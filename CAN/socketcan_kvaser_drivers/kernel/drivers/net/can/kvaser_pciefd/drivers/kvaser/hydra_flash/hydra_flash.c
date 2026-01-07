/*
**             Copyright 2023 by Kvaser AB, Molndal, Sweden
**                         http://www.kvaser.com
**
** This software is dual licensed under the following two licenses:
** BSD-new and GPLv2. You may use either one. See the included
** COPYING file for details.
**
** License: BSD-new
** ==============================================================================
** Redistribution and use in source and binary forms, with or without
** modification, are permitted provided that the following conditions are met:
**     * Redistributions of source code must retain the above copyright
**       notice, this list of conditions and the following disclaimer.
**     * Redistributions in binary form must reproduce the above copyright
**       notice, this list of conditions and the following disclaimer in the
**       documentation and/or other materials provided with the distribution.
**     * Neither the name of the <organization> nor the
**       names of its contributors may be used to endorse or promote products
**       derived from this software without specific prior written permission.
**
** THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
** AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
** IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
** ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
** LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
** CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
** SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
** BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER
** IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
** ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
** POSSIBILITY OF SUCH DAMAGE.
**
**
** License: GPLv2
** ==============================================================================
** This program is free software; you can redistribute it and/or modify
** it under the terms of the GNU General Public License as published by
** the Free Software Foundation; either version 2 of the License, or
** (at your option) any later version.
**
** This program is distributed in the hope that it will be useful,
** but WITHOUT ANY WARRANTY; without even the implied warranty of
** MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
** GNU General Public License for more details.
**
** You should have received a copy of the GNU General Public License
** along with this program; if not, write to the Free Software
** Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA
**
**
** IMPORTANT NOTICE:
** ==============================================================================
** This source code is made available for free, as an open license, by Kvaser AB,
** for use with its applications. Kvaser AB does not accept any liability
** whatsoever for any third party patent or other immaterial property rights
** violations that may result from any usage of this source code, regardless of
** the combination of source code and various applications that it can be used
** in, or with.
**
** -----------------------------------------------------------------------------
*/
#ifdef __KERNEL__
#include <linux/kernel.h>
#include <linux/types.h>
#include <linux/string.h>
#include <linux/crc32.h>
#include <linux/slab.h>
#include <linux/ktime.h>
#include <linux/pci.h>
//#include "pciefd_config.h"
#else
#include "crc32.h"
#include <string.h> /* memcpy */

#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))

#endif /* __KERNEL__ */

#include "k_assert.h"
#include "debugprint.h"
#include "util.h"
#include "spi_flash.h"
#include "kcan_ioctl_flash.h"
#include "hydra_imgheader.h"
#include "hydra_param_defs.h"
#include "hydra_flash.h"

#define SIMULATE_WRITE 0

#if SIMULATE_WRITE
#pragma message __FILE__ " is compiled in write simulation mode."
#endif

#define MAX_PARAM_NUM 256
#define PARAM_MAGIC   0xCAFEF00D
#define PARAM_SYS_VER 1
#define CHANNEL_NAME_PARAM_INDEX_FIRST (PARAM_USER_FIRST + 1)

#define DISPLAY_UPDATE_ACTIVE(ctx)   ((ctx)->device_ops->display_update_state((ctx)->data, true))
#define DISPLAY_UPDATE_INACTIVE(ctx) ((ctx)->device_ops->display_update_state((ctx)->data, false))

typedef struct {
    u32 magic; //PARAM_MAGIC indicate used
    u32 number;
    u32 len;
    u8 data[HYDRA_FLASH_PARAM_MAX_SIZE];
} kcc_param_t;

typedef struct {
    u32 version;
    u32 magic;
    u32 crc;
    kcc_param_t param[MAX_PARAM_NUM];
} kcc_param_image_t;

/* Helper array to get transducer type parameter id per channel index */
const int trans_type_index[] = {
PARAM_CHANNEL_A_TRANS_TYPE,
PARAM_CHANNEL_B_TRANS_TYPE,
PARAM_CHANNEL_C_TRANS_TYPE,
PARAM_CHANNEL_D_TRANS_TYPE,
PARAM_CHANNEL_E_TRANS_TYPE,
PARAM_CHANNEL_F_TRANS_TYPE,
PARAM_CHANNEL_G_TRANS_TYPE,
PARAM_CHANNEL_H_TRANS_TYPE,
};

static_assert(ARRAY_SIZE(trans_type_index) == HYDRA_FLASH_MAX_CARD_CHANNELS);

//======================================================================
//  Verify parameter image
//======================================================================
static int verify_param_image(kcc_param_image_t *img)
{
    u32 crc32;

    K_ASSERT(img != NULL);

    if ((img->version != PARAM_SYS_VER) || (img->magic != PARAM_MAGIC)) {
        DEBUGPRINT(1, "ERROR: %s version or magic error\n", __func__);
        DEBUGPRINT(1, "       version: got %d, expected %d\n", img->version, PARAM_SYS_VER);
        DEBUGPRINT(1, "       magic:   got %x, expected %x\n", img->magic, PARAM_MAGIC);
        return -6;
    }

    crc32 = calculateCRC32(img->param, sizeof(img->param));
    if (img->crc != crc32) {
        DEBUGPRINT(1, "ERROR: %s incorrect crc should be 0x%08x, is 0x%08x\n", __func__, img->crc,
                   crc32);
        return -6;
    }

    return HYDRA_FLASH_STAT_OK;
}

//======================================================================
//  Read a parameter
//======================================================================
static int read_param(const kcc_param_image_t *img, uint p_num, void *p_data, uint p_len)
{
    K_ASSERT(img != NULL);
    K_ASSERT(p_num < MAX_PARAM_NUM);
    K_ASSERT(p_data != NULL);
    K_ASSERT(p_len <= HYDRA_FLASH_PARAM_MAX_SIZE);

    if (img->param[p_num].magic != PARAM_MAGIC) {
        DEBUGPRINT(2, "Error: %s param no=%u expected param magic=%x got param magic=%x\n",
                   __func__, p_num, PARAM_MAGIC, img->param[p_num].magic);
        return HYDRA_FLASH_STAT_FAIL;
    }

    if (p_len != img->param[p_num].len) {
        DEBUGPRINT(1, "Error: %s param no.=%u param len=%u, actual_param len=%u\n", __func__, p_num,
                   p_len, img->param[p_num].len);
        return HYDRA_FLASH_STAT_FAIL;
    }

    memcpy(p_data, img->param[p_num].data, p_len);
    return HYDRA_FLASH_STAT_OK;
}

//======================================================================
// Initialize hydra_flash_ctx
//======================================================================
int HYDRA_FLASH_init(struct hydra_flash_ctx *ctx,
                     const struct hydra_flash_image_def *img_def,
                     const struct hydra_flash_device_ops *dev_ops,
                     void *data)
{
    K_ASSERT(ctx != NULL);
    K_ASSERT(img_def != NULL);
    ctx->image_def = img_def;
    ctx->device_ops = dev_ops;
    ctx->data = data;
    memset(&ctx->params, 0, sizeof(ctx->params));

    return HYDRA_FLASH_STAT_OK;
}

//======================================================================
// Deinitialize hydra_flash_ctx
//======================================================================
void HYDRA_FLASH_deinit(struct hydra_flash_ctx *ctx)
{
    if (ctx->flash_image) {
        DEBUGPRINT(3, "%s freeing image buffer\n", __func__);
        kfree(ctx->flash_image);
        ctx->flash_image = NULL;
    }
}

//======================================================================
// Read parameters from serial flash memory
//======================================================================
int HYDRA_FLASH_read_params(struct hydra_flash_ctx *ctx)
{
    kcc_param_image_t *img = NULL;
    unsigned int i;
    int status;
    timespec_t now;
    u32 duration_ms;

    K_ASSERT(ctx != NULL);
    TIMESPEC_GET(ctx->spif.time);

    img = kzalloc(sizeof(kcc_param_image_t), GFP_KERNEL);
    if (img == NULL) {
        DEBUGPRINT(1, "Failed to allocate memory.\n");
        return HYDRA_FLASH_STAT_NO_MEMORY;
    }

    status = SPI_FLASH_read(&ctx->spif, ctx->image_def->param_image_offset,
                            (u8 *)img, sizeof(kcc_param_image_t));

    if (status != SPI_FLASH_STATUS_SUCCESS) {
        DEBUGPRINT(1, "Error %d when reading parameter image.\n", status);
        goto error_exit;
    }

    status = verify_param_image(img);
    if (status != HYDRA_FLASH_STAT_OK)
        goto error_exit;

    status = read_param(img, PARAM_EAN_NUMBER, &ctx->params.ean, PARAM_EAN_NUMBER_LEN);
    if (status != HYDRA_FLASH_STAT_OK)
        goto error_exit;

    status = read_param(img, PARAM_HW_REVISION, &ctx->params.hw_rev_major, PARAM_HW_REVISION_LEN);
    if (status != HYDRA_FLASH_STAT_OK)
        goto error_exit;

    status = read_param(img, PARAM_SERIAL_NUMBER, &ctx->params.serial_number, PARAM_SERIAL_NUMBER_LEN);
    if (status != HYDRA_FLASH_STAT_OK)
        goto error_exit;

    status = read_param(img, PARAM_HW_TYPE, &ctx->params.hw_type, PARAM_HW_TYPE_LEN);
    if (status != HYDRA_FLASH_STAT_OK)
        goto error_exit;

    status = read_param(img, PARAM_MAX_BITRATE, &ctx->params.max_bitrate, PARAM_MAX_BITRATE_LEN);
    if (status != HYDRA_FLASH_STAT_OK)
        goto error_exit;

#ifdef FPGA_META_OVERRIDES_FLASH
    pr_warn("INFO: No. of channels was NOT read from flash!\n");
#else
    status =
        read_param(img, PARAM_NUMBER_CHANNELS, &ctx->params.nr_channels, PARAM_NUMBER_CHANNELS_LEN);
    if (status != HYDRA_FLASH_STAT_OK)
        goto error_exit;
#endif

    if (ctx->params.nr_channels == 0) {
        DEBUGPRINT(1, "Error: nr_channels is zero.\n");
        goto error_exit;
    }

    if (ctx->params.nr_channels > HYDRA_FLASH_MAX_CARD_CHANNELS) {
        DEBUGPRINT(1, "Error: nr_channels > HYDRA_FLASH_MAX_CARD_CHANNELS (%u > %u)\n",
                   ctx->params.nr_channels, HYDRA_FLASH_MAX_CARD_CHANNELS);
        goto error_exit;
    }

    if (ctx->params.nr_channels > ARRAY_SIZE(trans_type_index)) {
        DEBUGPRINT(1, "Error: nr_channels > ARRAY_SIZE(trans_type_index) (%u > %zu)\n",
                   ctx->params.nr_channels, ARRAY_SIZE(trans_type_index));
        goto error_exit;
    }

    for (i = 0; i < ctx->params.nr_channels; i++) {
        status = read_param(img, trans_type_index[i], &ctx->params.trans_type[i],
                            PARAM_CHANNEL_TRANS_TYPE_LEN);
        if (status != HYDRA_FLASH_STAT_OK)
            goto error_exit;

        // These are optional, hence we don't check the return code
        read_param(img, CHANNEL_NAME_PARAM_INDEX_FIRST + i, ctx->params.cust_channel_name[i],
                   sizeof(ctx->params.cust_channel_name[i]));
    }
    kfree(img);
    TIMESPEC_GET(now);
    duration_ms = TIMESPEC_MS_DELTA(now, ctx->spif.time);
    DEBUGPRINT(3, "Reading parameters took %u.%03u seconds.\n", duration_ms / 1000,
               duration_ms % 1000);

    return HYDRA_FLASH_STAT_OK;

error_exit:
    if (img != NULL)
        kfree(img);
    return HYDRA_FLASH_STAT_FAIL;
}


//======================================================================
//  Calculate firmware image checksum
//======================================================================
static u32 calc_fw_checksum(u8 *buffer, u32 size)
{
#ifdef __KERNEL__
    return crc32(0xffffffff, buffer, size) ^ 0xffffffff;
#else
    return crc32Calc(buffer, size);
#endif /* __KERNEL__ */
}

//======================================================================
//  Verify firmware image EAN
//======================================================================
static int verify_fw_ean(u64 ean, const HydraImgHeader *sysHeader)
{
    if ((ean >> 32) != sysHeader->eanHi)
        return -1;
    if ((ean & 0xffffffff) != sysHeader->eanLo)
        return -1;
    return 0;
}

//======================================================================
//  Write firmware image
//======================================================================
static int write_fw_image(struct hydra_flash_ctx *ctx, u32 addr, const u8 *buf, u32 num_bytes)
{
    int status;

    K_ASSERT(ctx != NULL);
    K_ASSERT(&ctx->spif != NULL);
    K_ASSERT(buf != NULL);

    if ((addr + num_bytes) > (ctx->image_def->fpga_image_offset + ctx->image_def->fpga_image_size_max)) {
        DEBUGPRINT(1, "%s FPGA image size too big, aborting\n", __func__);
        return FIRMWARE_ERROR_INVALID_ARG;
    }

#if !SIMULATE_WRITE
    status = SPI_FLASH_erase_multi_64K(&ctx->spif, addr, num_bytes, 5000);
    if (status != SPI_FLASH_STATUS_SUCCESS) {
        DEBUGPRINT(1, "%s Error, flash erase failed with %d, aborting", __func__, status);
        return FIRMWARE_ERROR_FLASH_FAILED;
    }

    status = SPI_FLASH_write_multi_page(&ctx->spif, addr, buf, num_bytes);
    if (status != SPI_FLASH_STATUS_SUCCESS) {
        DEBUGPRINT(1, "%s Error, page write failed with %d, aborting.", __func__, status);
        return FIRMWARE_ERROR_FLASH_FAILED;
    }
#else
    NOT_USED(status);
    DEBUGPRINT(1, "Simulating erase between 0x%08X - 0x%08X\n", addr,
               addr + (DIV_ROUND_UP(num_bytes, (64 * 1024U)) * (64 * 1024U)));
    DEBUGPRINT(1, "Simulating write of %u bytes at 0x%08X - 0x%08X\n", num_bytes, addr,
               addr + num_bytes);
#endif

    return FIRMWARE_STATUS_OK;
}

//======================================================================
//  Verify firmware image
//======================================================================
static int verify_fw_image(struct hydra_flash_ctx *ctx, u32 addr, const u8 *buf, u32 num_bytes)
{
#if !SIMULATE_WRITE
    int status;

    status = SPI_FLASH_compare(&ctx->spif, addr, buf, num_bytes);
    if (status != SPI_FLASH_STATUS_SUCCESS) {
        DEBUGPRINT(1, "Warning: Image does NOT match current.\n");
        return FIRMWARE_ERROR_VERIFY_DIFF;
    }
#else
    NOT_USED(ctx);
    NOT_USED(addr);
    NOT_USED(buf);
    NOT_USED(num_bytes);
#endif
    DEBUGPRINT(2, "Image matches current.\n");
    return FIRMWARE_STATUS_OK;
}

//======================================================================
//  Trig reprogram of device
//======================================================================
static int trigger_update(struct hydra_flash_ctx *ctx)
{
    int status = FIRMWARE_STATUS_OK;

#if !SIMULATE_WRITE
    // firmware_upgrade_trigger_update is optional, call if it is set
    if (ctx->device_ops && ctx->device_ops->firmware_upgrade_trigger_update)
        status = ctx->device_ops->firmware_upgrade_trigger_update(ctx->data);
#endif

    return status;
}

//======================================================================
//  Write firmware image, then read it back and verify
//======================================================================
static int write_verify_fw_image(struct hydra_flash_ctx *ctx, u32 addr, const u8 *buf, u32 num_bytes)
{
    int status;

    status = write_fw_image(ctx, addr, buf, num_bytes);
    if (status != FIRMWARE_STATUS_OK) {
        DEBUGPRINT(1, "Error: %s write failed: %d\n", __func__, status);
        return status;
    }

    status = verify_fw_image(ctx, addr, buf, num_bytes);
    if (status != FIRMWARE_STATUS_OK) {
        DEBUGPRINT(1, "Error: %s compare failed\n", __func__);
    }

    return status;
}


//======================================================================
//  Do firmware update by processing IOCTL commands
//======================================================================
int HYDRA_FLASH_update_fw_ioctl(struct hydra_flash_ctx *ctx, KCAN_FLASH_PROG *fp)
{
    switch (fp->tag) {
    case FIRMWARE_DOWNLOAD_STARTUP:
        DEBUGPRINT(2, "IOCTL event: FIRMWARE_DOWNLOAD_STARTUP\n");
        if (ctx->flash_image == NULL) {
            ctx->flash_image = kzalloc(ctx->image_def->fpga_image_size_max, GFP_KERNEL);
            if (ctx->flash_image == NULL) {
                DEBUGPRINT(1, "Error: %s Out of memory.\n", __func__);
                return HYDRA_FLASH_STAT_NO_MEMORY;
            }
        }
        memset(ctx->flash_image, 0xff, ctx->image_def->fpga_image_size_max);

        ctx->spif.dry_run = (bool)fp->x.setup.dryrun;
        fp->x.setup.flash_procedure_version = 0;
        fp->x.setup.buffer_size = KCAN_FLASH_DOWNLOAD_CHUNK;
        if (ctx->device_ops && ctx->device_ops->display_update_state)
            DISPLAY_UPDATE_ACTIVE(ctx);
        break;

    case FIRMWARE_DOWNLOAD_WRITE:
        //DEBUGPRINT(2, "IOCTL event: FIRMWARE_DOWNLOAD_WRITE\n");
        if (ctx->flash_image && ((fp->x.data.address + fp->x.data.len) < ctx->image_def->fpga_image_size_max)) {
            memcpy(ctx->flash_image + fp->x.data.address, fp->x.data.data, fp->x.data.len);
        } else {
            fp->status = FIRMWARE_ERROR_ADDR;
            goto error_exit;
        }
        break;

    case FIRMWARE_DOWNLOAD_COMMIT: {
        HydraImgHeader *sysHeader;
        int numberOfImages;
        int i;

        DEBUGPRINT(2, "IOCTL event: FIRMWARE_DOWNLOAD_COMMIT\n");
        if (ctx->flash_image == NULL) {
            fp->status = FIRMWARE_ERROR_ADDR;
            goto error_exit;
        }

        sysHeader = (HydraImgHeader *)ctx->flash_image;
        /* validate image header */
        if (sysHeader->hdCrc !=
            calc_fw_checksum(ctx->flash_image, sizeof(HydraImgHeader) - sizeof(u32))) {
            fp->status = FIRMWARE_ERROR_BAD_CRC;
            goto error_exit;
        }

        /* validate image type */
        if (sysHeader->imgType != IMG_TYPE_SYSTEM_CONTAINER) {
            DEBUGPRINT(1, "Error: image type %d invalid\n", sysHeader->imgType);
            fp->status = FIRMWARE_ERROR_ADDR;
            goto error_exit;
        }

        /* ensure image matches current hardware */
        if (verify_fw_ean(ctx->params.ean, sysHeader) != 0) {
            DEBUGPRINT(1, "Error: image EAN does not match device\n");
            fp->status = FIRMWARE_ERROR_FLASH_FAILED;
            goto error_exit;
        }

        numberOfImages = *(ctx->flash_image + sizeof(HydraImgHeader));
        DEBUGPRINT(3, "No. of images = %d\n", numberOfImages);

        for (i = 0; i < numberOfImages; i++) {
            /* validate full hydra image */
            if (calc_fw_checksum(ctx->flash_image + sizeof(HydraImgHeader), sysHeader->imgLength) ==
                sysHeader->imgCrc) {
                ImageContainerInfo *imgInfo;
                HydraImgHeader *imgHeader;
                u8 *startAddr;

                imgInfo = (ImageContainerInfo *)(ctx->flash_image + sizeof(HydraImgHeader) + 4);
                imgHeader = (HydraImgHeader *)(ctx->flash_image + imgInfo[i].imgStartAddr);
                startAddr = ctx->flash_image + imgInfo[i].imgStartAddr + sizeof(HydraImgHeader);
                DEBUGPRINT(3, "Sys image validated. (V.%08x)\n", sysHeader->version);

                if (!ctx->spif.dry_run) {
                    fp->status = write_verify_fw_image(ctx, imgHeader->prgAddr, startAddr,
                                                       imgHeader->imgLength);
                    if (fp->status == FIRMWARE_STATUS_OK) {
                        DEBUGPRINT(3, "Flashing image %i of %i was completed with status %d.\n",
                                   i + 1, numberOfImages, fp->status);
                    } else {
                        DEBUGPRINT(3, "Flashing image %i of %i failed with status %d, aborting.\n",
                                   i + 1, numberOfImages, fp->status);
                        goto error_exit;
                    }
                } else {
                    DEBUGPRINT(3, "Dry-run  %i of %i.\n", i + 1, numberOfImages);
                }
            } else {
                DEBUGPRINT(1, "Error: Image crc check failed. (V.%08x)\n", sysHeader->version);
                fp->status = FIRMWARE_ERROR_BAD_CRC;
                goto error_exit;
            }
        }
        if (!ctx->spif.dry_run) {
            fp->status = trigger_update(ctx);
            if (fp->status != FIRMWARE_STATUS_OK)
                goto error_exit;
        }
        break;
    }

    case FIRMWARE_DOWNLOAD_FINISH:
        DEBUGPRINT(2, "IOCTL event: FIRMWARE_DOWNLOAD_FINISH\n");
        if (ctx->flash_image) {
            DEBUGPRINT(3, "freeing image buffer\n");
            kfree(ctx->flash_image);
            ctx->flash_image = NULL;
            if (ctx->device_ops && ctx->device_ops->display_update_state)
                DISPLAY_UPDATE_INACTIVE(ctx);
        } else {
            fp->status = FIRMWARE_ERROR_ADDR;
            goto error_exit;
        }
        break;

    case FIRMWARE_DOWNLOAD_ERASE:
        DEBUGPRINT(2, "IOCTL event: FIRMWARE_DOWNLOAD_ERASE\n");
        /* not supported */
        break;

    default:
        DEBUGPRINT(1, "Error: %s, Unknown tag %d\n", __func__, fp->tag);
        goto error_exit;
    }

    return HYDRA_FLASH_STAT_OK;

error_exit:
    if (ctx->flash_image) {
        DEBUGPRINT(3, "%s: Freeing image buffer.\n", __func__);
        kfree(ctx->flash_image);
        ctx->flash_image = NULL;
    }
    if (ctx->device_ops && ctx->device_ops->display_update_state)
        DISPLAY_UPDATE_INACTIVE(ctx);
    return HYDRA_FLASH_STAT_FAIL;
}

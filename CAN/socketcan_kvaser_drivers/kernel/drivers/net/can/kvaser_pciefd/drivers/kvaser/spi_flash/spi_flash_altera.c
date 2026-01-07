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

/**
 * Kvaser Altera SPI flash implementation
 * Compatible with Altera EPCQ16A SPI flash
 */


#ifdef __KERNEL__
#include <linux/slab.h>
#endif /* __KERNEL__ */
#include "k_assert.h"
#include "debugprint.h"
#include "util.h"
#include "altera_avalon_epcs_flash_controller.h"
#include "altera_avalon_spi.h"
#include "epcs_commands.h"
#include "spi_flash.h"

#define SPI_FLASH_ALTERA_EPCQ16A_JEDEC_ID 0x00000015 /* Note SPI flash is not JEDEC compliant */

#define SPI_FLASH_ALTERA_SR_IS_READY_MASK 0x01 /* Ready mask */

#define DONT_CARE 0x00u

/* Progress in % logged during flash operations */
#define PERC_STEP_WRITE   20
#define PERC_STEP_ERASE   20

/**
 * @brief Initialize and configure SPI comm.
 *
 * @param spif      Pointer to spi_flash struct
 * @param base_addr Pointer to the SPI IOMEM block
 * @return int      SPI_FLASH_STATUS_SUCCESS or error code != 0
 */
static int SPI_FLASH_altera_init(struct spi_flash *spif, void __iomem *base_addr)
{
    alt_flash_epcs_dev *spi;
    int ret;

    K_ASSERT(spif != NULL);
    K_ASSERT(base_addr != NULL);

    spif->hnd = kzalloc(sizeof(alt_flash_epcs_dev), GFP_KERNEL);
    if (spif->hnd == NULL) {
        return SPI_FLASH_STATUS_MALLOC;
    }

    spi = spif->hnd;
    ret = alt_epcs_flash_init(spi, base_addr);
    if (ret != 0) {
        kfree(spif->hnd);
    }
    // TODO: Convert ret to SPI_FLASH_STATUS_
    return ret;
}

/**
 * @brief Deinitialize SPI comm.
 *
 * @param spif      Pointer to spi_flash struct
 */
static void SPI_FLASH_altera_deinit(struct spi_flash *spif)
{
    K_ASSERT(spif != NULL);

    if (spif->hnd != NULL) {
        kfree(spif->hnd);
        spif->hnd = NULL;
    }
}

/**
 * @brief Dummy function for API compatibility
 *
 * @param spif      Pointer to spi_flash struct (not used)
 * @return int      SPI_FLASH_STATUS_SUCCESS
 */
static int SPI_FLASH_altera_start(struct spi_flash *spif)
{
    NOT_USED(spif);
    return 0;
}

/**
 * @brief Dummy function for API compatibility
 *
 * @param spif      Pointer to spi_flash struct (not used)
 * @return int      SPI_FLASH_STATUS_SUCCESS
 */
static int SPI_FLASH_altera_stop(struct spi_flash *spif)
{
    NOT_USED(spif);
    return 0;
}

/**
 * @brief Read the status register of the Flash.
 *
 * @param spif      Pointer to spi_flash struct
 * @param status    Pointer to status return variable
 * @return int      SPI_FLASH_STATUS_SUCCESS or error code != 0
 */
static int SPI_FLASH_altera_get_status(struct spi_flash *spif, u8 *status)
{
    alt_flash_epcs_dev *spi;

    K_ASSERT(spif != NULL);
    K_ASSERT(spif->hnd != NULL);

    spi = spif->hnd;
    *status = epcs_read_status_register(spi->register_base);

    return 0;
}

/**
 * @brief Wait until the serial flash is ready to accept a command
 *
 * @param spif          Pointer to spi_flash struct
 * @param timeout_ms    Timeout in ms
 * @return int          SPI_FLASH_STATUS_SUCCESS or error code != 0
 */
static int SPI_FLASH_altera_wait_ready(struct spi_flash *spif, u32 timeout_ms)
{
    u8 status_reg;
    int res;
    timespec_t timeout;

    K_ASSERT(spif != NULL);
    K_ASSERT(spif->hnd != NULL);
    K_ASSERT(timeout_ms > 0);

    TIMESPEC_GET(timeout);
    TIMESPEC_ADD_MSEC(timeout, timeout_ms);
    do {
        res = SPI_FLASH_altera_get_status(spif, &status_reg);
        if (res)
            return res;

        if (status_reg & SPI_FLASH_ALTERA_SR_IS_READY_MASK)
            return SPI_FLASH_STATUS_SUCCESS;

        MSLEEP_SHORT(1);
    } while (TIMESPEC_IS_BEFORE(timeout));

    DEBUGPRINT(3, "%s: Timeout after %u ms!\n", __func__, timeout_ms);
    return SPI_FLASH_STATUS_TIMEOUT;
}

/**
 * @brief Enable writes to the serial flash memory.
 *
 * @param spif  Pointer to spi_flash struct
 * @return int  SPI_FLASH_STATUS_SUCCESS or error code != 0
 */
static int SPI_FLASH_altera_write_enable(struct spi_flash *spif)
{
    alt_flash_epcs_dev *spi;

    K_ASSERT(spif != NULL);
    K_ASSERT(spif->hnd != NULL);

    spi = spif->hnd;
    epcs_write_enable(spi->register_base);
    return 0;
}

/**
 * @brief Disable writes to the serial flash memory.
 *
 * @param spif  Pointer to spi_flash struct
 * @return int  SPI_FLASH_STATUS_SUCCESS or error code != 0
 */
static int SPI_FLASH_altera_write_disable(struct spi_flash *spif)
{
    alt_flash_epcs_dev *spi;

    K_ASSERT(spif != NULL);
    K_ASSERT(spif->hnd != NULL);

    spi = spif->hnd;
    epcs_write_disable(spi->register_base);
    return 0;
}

/**
 * @brief Get JEDEC id
 *
 * @param spif      Pointer to spi_flash struct
 * @param jedec_id  JEDEC id
 * @return          SPI_FLASH_STATUS_SUCCESS or error code != 0
 */
static int SPI_FLASH_altera_get_jedec(struct spi_flash *spif, u32 *jedec_id)
{
    alt_flash_epcs_dev *spi;

    K_ASSERT(spif != NULL);
    K_ASSERT(spif->hnd != NULL);
    K_ASSERT(jedec_id != NULL);

    spi = spif->hnd;
    *jedec_id = epcs_read_device_id(spi->register_base);

    return 0;
}

/**
 * @brief Verify flash JEDEC id
 *
 * @param spif      Pointer to spi_flash struct
 * @return true     If expected JEDEC id
 * @return false    If read fails or unexpected JEDEC id
 */
static bool SPI_FLASH_altera_verify_jedec(struct spi_flash *spif)
{
    u32 jedec_id;

    if (SPI_FLASH_altera_get_jedec(spif, &jedec_id))
        return false;

    return jedec_id == SPI_FLASH_ALTERA_EPCQ16A_JEDEC_ID;
}

/**
 * @brief Erase a 64 kiB block
 *
 * @param spif       Pointer to spi_flash struct
 * @param addr       Start address of block
 * @param timeout_ms Timeout in ms
 * @return int       SPI_FLASH_STATUS_SUCCESS or error code != 0
 *
 */
static int SPI_FLASH_altera_erase_64K(struct spi_flash *spif, u32 addr, u32 timeout_ms)
{
    alt_flash_epcs_dev *spi;
    alt_flash_dev *spi_dev;
    int ret;

    // TODO implement timeout
    NOT_USED(timeout_ms);

    K_ASSERT(spif != NULL);
    K_ASSERT(spif->hnd != NULL);

    spi = spif->hnd;
    spi_dev = &spi->dev;

    ret = SPI_FLASH_altera_write_enable(spif);
    if (ret != SPI_FLASH_STATUS_SUCCESS)
        return ret;

    ret = alt_epcs_flash_erase_block(spi_dev, addr);
    // TODO convert ret to SPI_FLASH_STATUS_

    return ret;
}

/**
 * @brief Erase one or more 64 kiB blocks
 *
 * @param spif       Pointer to spi_flash struct
 * @param addr       Start address of block, must be aligned on a 64 kiB boundary.
 * @param num_bytes  Number of bytes to erase, will be rounded up to a multiple of 64 kiB.
 * @param timeout_ms Timeout in ms
 *
 * @return int       SPI_FLASH_STATUS_SUCCESS or error code != 0
 */
static int SPI_FLASH_altera_erase_multi_64K(struct spi_flash *spif, u32 addr, u32 num_bytes,
                                     u32 timeout_ms)
{
    const u32 chunk_size = 64 * 1024U;
    u32 offset;
    u32 perc_reported = 0;

    if (num_bytes > 0)
        num_bytes = round_up(num_bytes, chunk_size);

    for (offset = 0U; offset < num_bytes; offset += chunk_size) {
        u32 perc;
        int ret = SPI_FLASH_altera_erase_64K(spif, addr + offset, timeout_ms);

        if (ret != SPI_FLASH_STATUS_SUCCESS) {
            DEBUGPRINT(3, "%s: Erasing 64K block 0x%08X - 0x%08X\n failed with %d, aborting",
                       __func__, addr, addr + offset, ret);
            return ret;
        }

        perc = (100 * (offset + chunk_size)) / num_bytes;
        if ((perc - perc_reported >= PERC_STEP_ERASE) || (perc == 100)) {
            if (((offset == 0) && (perc == 100)) || (perc_reported == 100))
                continue;
            DEBUGPRINT(1, "Erasing flash memory %3u%%\n", perc);
            perc_reported = perc;
        }
    }

    return SPI_FLASH_STATUS_SUCCESS;
}

/**
 * @brief Write up to 256 bytes of data to a specified location in the serial flash memory.
 *
 * @param spif      Pointer to spi_flash struct
 * @param addr      Start address in flash to write to, must be aligned on a 256 byte boundary.
 * @param buf       Pointer to buffer containing data to write
 * @param num_bytes The number of bytes to be written (<= 256)
 *
 * @return int      SPI_FLASH_STATUS_SUCCESS or error code != 0
 */
static int SPI_FLASH_altera_write_page(struct spi_flash *spif, u32 addr, const u8 *buf, u32 num_bytes)
{
    alt_flash_epcs_dev *spi;
    alt_flash_dev *spi_dev;
    int ret;

    K_ASSERT(spif != NULL);
    K_ASSERT(spif->hnd != NULL);
    spi = spif->hnd;
    spi_dev = &spi->dev;

    ret = SPI_FLASH_altera_write_enable(spif);
    if (ret != SPI_FLASH_STATUS_SUCCESS)
        return ret;
    ret = alt_epcs_flash_write_block(spi_dev, DONT_CARE, addr, buf, num_bytes);
    // TODO convert ret to SPI_FLASH_STATUS_

    return ret;
}

/**
 * @brief Write multiple pages of up to 256 bytes of data to a specified
 *        location in the serial flash memory.
 *
 * @param spif      Pointer to spi_flash struct
 * @param addr      Start address in flash to write to, must be aligned on a 256 byte boundary.
 * @param buf       Pointer to buffer containing data to write
 * @param num_bytes The number of bytes to be written (<= 256)
 *
 * @return int      SPI_FLASH_STATUS_SUCCESS or error code != 0
 */
static int SPI_FLASH_altera_write_multi_page(struct spi_flash *spif, u32 addr, const u8 *buf,
                                      u32 num_bytes)
{
    u32 offset;
    u32 perc_reported = 0;
    alt_flash_epcs_dev *spi;

    K_ASSERT(spif != NULL);
    K_ASSERT(spif->hnd != NULL);
    spi = spif->hnd;

    for (offset = 0U; offset < num_bytes; offset += spi->page_size) {
        u32 perc;
        u32 chunk_size = min(num_bytes - offset, spi->page_size);
        int ret = SPI_FLASH_altera_write_page(spif, addr + offset, buf + offset, chunk_size);

        if (ret != SPI_FLASH_STATUS_SUCCESS) {
            DEBUGPRINT(2, "%s Error, page write failed with %d, aborting.", __func__, ret);
            return ret;
        }

        perc = (100 * (offset + chunk_size)) / num_bytes;
        if ((perc - perc_reported >= PERC_STEP_WRITE) || (perc == 100)) {
            if (((offset == 0) && (perc == 100)) || (perc_reported == 100))
                continue;
            DEBUGPRINT(1, "Writing flash memory %3u%%\n", perc);
            perc_reported = perc;
        }
    }

    return SPI_FLASH_STATUS_SUCCESS;
}

/**
* @brief Read multiple pages of up to 256 bytes of data from a
*        specified location in the serial flash memory.
*
* @param spif      Pointer to spi_flash struct
* @param addr      Start address in flash to read from, must be aligned on a 256 byte boundary.
* @param buf       Pointer to buffer to read data into
* @param num_bytes The number of bytes to be read
*
* @return int      SPI_FLASH_STATUS_SUCCESS or error code != 0
*/
static int SPI_FLASH_altera_read(struct spi_flash *spif, u32 addr, u8 *buf, u32 num_bytes)
{
    alt_flash_epcs_dev *spi;
    alt_flash_dev *spi_dev;
    int ret;

    K_ASSERT(spif != NULL);
    K_ASSERT(spif->hnd != NULL);
    spi = spif->hnd;
    spi_dev = &spi->dev;

    ret = alt_epcs_flash_read(spi_dev, addr, buf, num_bytes);
    // TODO convert ret to SPI_FLASH_STATUS_

    return ret;
}

/**
* @brief Compare the contents of a buffer with the contents of a
*        specified location in the serial flash memory.
*
* @param spif      Pointer to spi_flash struct
* @param addr      Start address in flash to read from, must be aligned on a 256 byte boundary.
* @param buf       Pointer to buffer containing data to compare with flash contents
* @param num_bytes The number of bytes to compare
*
* @return int      If buffers are equal: SPI_FLASH_STATUS_SUCCESS
*                  If buffers are not equal: -1
*                  If error: error code > 0
*/
static int SPI_FLASH_altera_compare(struct spi_flash *spif, u32 addr, const u8 *buf, u32 num_bytes)
{
    alt_flash_epcs_dev *spi;
    alt_flash_dev *spi_dev;

    K_ASSERT(spif != NULL);
    K_ASSERT(spif->hnd != NULL);
    spi = spif->hnd;
    spi_dev = &spi->dev;

    return alt_epcs_flash_memcmp(spi_dev, buf, addr, num_bytes);
}

const struct SPI_FLASH_ops SPI_FLASH_altera_ops = {
    .init = SPI_FLASH_altera_init,
    .deinit = SPI_FLASH_altera_deinit,
    .start = SPI_FLASH_altera_start,
    .stop = SPI_FLASH_altera_stop,
    .get_status = SPI_FLASH_altera_get_status,
    .wait_ready = SPI_FLASH_altera_wait_ready,
    .write_enable = SPI_FLASH_altera_write_enable,
    .write_disable = SPI_FLASH_altera_write_disable,
    .get_jedec = SPI_FLASH_altera_get_jedec,
    .verify_jedec = SPI_FLASH_altera_verify_jedec,
    .erase_64K = SPI_FLASH_altera_erase_64K,
    .erase_multi_64K = SPI_FLASH_altera_erase_multi_64K,
    .write_page = SPI_FLASH_altera_write_page,
    .write_multi_page = SPI_FLASH_altera_write_multi_page,
    .read = SPI_FLASH_altera_read,
    .compare = SPI_FLASH_altera_compare,
};

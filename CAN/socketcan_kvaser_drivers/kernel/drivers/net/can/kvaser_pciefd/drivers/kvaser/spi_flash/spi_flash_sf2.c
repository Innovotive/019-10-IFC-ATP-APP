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

/** \file
 *
 * \brief SPI flash driver for Microchip M2S025 with IS25LP016 SPI flash
 */

#ifdef __KERNEL__
#include <linux/delay.h>
#include <linux/slab.h>
#else
#include <string.h> /* memcpy */
#endif /* __KERNEL__ */
#include "k_assert.h"
#include "debugprint.h"
#include "util.h"
#include "sf2_spi.h"
#include "spi_flash.h"

/* Configuration. */

/** SPI Flash JEDEC ID. */
#define SPI_FLASH_JEDEC_ID_IS25LP016  0x009D6015
/** SPI Flash page size. */
#define SPI_FLASH_PAGE_SIZE           256U
/** SPI Flash sector size. */
#define SPI_FLASH_SECTOR_SIZE         (64 * 1024U)
/** Timeout in milliseconds for SPI transfers. */
#define SPI_FLASH_TRANSFER_TIMEOUT_ms 1000

/* SPI flash opcodes. */

/** SPI Flash opcode Page program. */
#define SPI_OPCODE_PP        0x02
/** SPI Flash opcode Write disable. */
#define SPI_OPCODE_WRDI      0x04
/** SPI Flash opcode Read status register. */
#define SPI_OPCODE_RDSR      0x05
/** SPI Flash opcode Write enable. */
#define SPI_OPCODE_WREN      0x06
/** SPI Flash opcode Read data at high frequency. */
#define SPI_OPCODE_READ_FAST 0x0B
/** SPI Flash opcode Read JEDEC ID. */
#define SPI_OPCODE_RDID      0x9F
/** SPI Flash opcode Sector erase. */
#define SPI_OPCODE_SE        0xD8

/* SPI Flash Status register contents. */

/** SPI Flash status Write in progress. */
#define SPI_SR_WIP BIT(0)

/* Progress in % logged during flash operations */
#define PERC_STEP_READ    20
#define PERC_STEP_WRITE   20
#define PERC_STEP_ERASE   20
#define PERC_STEP_COMPARE 20

/* ensure success status compatibility */
static_assert(SPI_FLASH_STATUS_SUCCESS == SF2_SPI_STATUS_SUCCESS);

/* Ensure sector & page size as expected*/
static_assert(SPI_FLASH_SECTOR_SIZE == 64 * 1024U);
static_assert(SPI_FLASH_PAGE_SIZE == 256U);

/* Interface functions. */

/**
 * @brief Initialize the SPI controller.
 *
 * @param[in,out] spif   Pointer to an spi_flash structure.
 * @param[in] base_addr  Base address of the SPI0 registers.
 *
 * @return int           SPI_FLASH_STATUS_SUCCESS.
 */
static int SPI_FLASH_sf2_init(struct spi_flash *spif, void __iomem *base_addr)
{
    K_ASSERT(spif != NULL);
    K_ASSERT(base_addr != NULL);

    spif->hnd = kzalloc(sizeof(struct SF2_SPI), GFP_KERNEL);
    if (spif->hnd == NULL)
        return SPI_FLASH_STATUS_MALLOC;

    SF2_SPI_init(spif->hnd, base_addr);
    return SPI_FLASH_STATUS_SUCCESS;
}

/**
 * @brief Deinitialize the SPI controller.
 *
 * @param[in,out] spif   Pointer to an spi_flash structure.
 */
static void SPI_FLASH_sf2_deinit(struct spi_flash *spif)
{
    K_ASSERT(spif != NULL);

    if (spif->hnd != NULL) {
        kfree(spif->hnd);
        spif->hnd = NULL;
    }
}

/**
 * @brief Start SPI controller.
 *
 * Note: Does nothing.
 *
 * @param[in] spif  Pointer to an spi_flash structure.
 *
 * @return int      SPI_FLASH_STATUS_SUCCESS.
 */
static int SPI_FLASH_sf2_start(struct spi_flash *spif)
{
    NOT_USED(spif);
    return SPI_FLASH_STATUS_SUCCESS;
}

/**
 * @brief Stop SPI controller.
 *
 * Note: Does Nothing.
 *
 * @param[in] spif  Pointer to an spi_flash structure.
 *
 * @return int      SPI_FLASH_STATUS_SUCCESS.
 */
static int SPI_FLASH_sf2_stop(struct spi_flash *spif)
{
    NOT_USED(spif);
    return SPI_FLASH_STATUS_SUCCESS;
}

/**
 * @brief Read SPI flash status register.
 *
 * @param[in] spif      Pointer to an spi_flash structure.
 * @param[out] status   Pointer to output data.
 *
 * @return int          SPI_FLASH_STATUS_SUCCESS or
 *                      SPI_FLASH_STATUS_TIMEOUT.
 */
static int SPI_FLASH_sf2_get_status(struct spi_flash *spif, u8 *status)
{
    u8 command = SPI_OPCODE_RDSR;
    int ret;

    K_ASSERT(spif != NULL);
    K_ASSERT(spif->hnd != NULL);
    K_ASSERT(status != NULL);

    SF2_SPI_cs_set(spif->hnd);
    ret = SF2_SPI_transfer(spif->hnd, &command, sizeof(command), status, sizeof(*status),
                           SPI_FLASH_TRANSFER_TIMEOUT_ms);
    SF2_SPI_cs_clear(spif->hnd);

    return ret;
}

/**
 * @brief Wait for SPI flash to complete write.
 *
 * Wait for the SPI flash status register to clear the
 * Write in progress bit.
 *
 * @param[in] spif        Pointer to an spi_flash structure.
 * @param[in] timeout_ms  The timeout in milliseconds.
 *
 * @return int            SPI_FLASH_STATUS_SUCCESS or
 *                        SPI_FLASH_STATUS_TIMEOUT.
 */
static int SPI_FLASH_sf2_wait_ready(struct spi_flash *spif, u32 timeout_ms)
{
    u8 command = SPI_OPCODE_RDSR;
    u8 status;
    timespec_t timeout;
    int ret;

    K_ASSERT(spif != NULL);
    K_ASSERT(spif->hnd != NULL);
    K_ASSERT(timeout_ms > 0);

    TIMESPEC_GET(timeout);
    TIMESPEC_ADD_MSEC(timeout, timeout_ms);

    do {
        ret = SF2_SPI_transfer(spif->hnd, &command, sizeof(command), &status, sizeof(status),
                               timeout_ms);
        if (ret)
            return ret;

        if ((status & SPI_SR_WIP) == 0)
            return SPI_FLASH_STATUS_SUCCESS;

        MSLEEP_SHORT(1);
    } while (TIMESPEC_IS_BEFORE(timeout));

    return SPI_FLASH_STATUS_TIMEOUT;
}

/**
 * @brief Write enable SPI flash.
 *
 * Send Write Enable command to SPI flash.
 *
 * @param[in] spif  Pointer to an spi_flash structure.
 *
 * @return int      SPI_FLASH_STATUS_SUCCESS or
 *                  SPI_FLASH_STATUS_TIMEOUT.
 */
static int SPI_FLASH_sf2_write_enable(struct spi_flash *spif)
{
    u8 command = SPI_OPCODE_WREN;
    int ret;

    K_ASSERT(spif != NULL);
    K_ASSERT(spif->hnd != NULL);

    SF2_SPI_cs_set(spif->hnd);
    ret = SF2_SPI_transfer(spif->hnd, &command, sizeof(command), NULL, 0,
                           SPI_FLASH_TRANSFER_TIMEOUT_ms);
    SF2_SPI_cs_clear(spif->hnd);

    return ret;
}

/**
 * @brief Disable write for SPI flash.
 *
 * Send Write disable command to SPI flash.
 *
 * @param[in] spif  Pointer to an spi_flash structure.
 *
 * @return int      SPI_FLASH_STATUS_SUCCESS or
 *                  SPI_FLASH_STATUS_TIMEOUT.
 */
static int SPI_FLASH_sf2_write_disable(struct spi_flash *spif)
{
    u8 command = SPI_OPCODE_WRDI;
    int ret;

    K_ASSERT(spif != NULL);
    K_ASSERT(spif->hnd != NULL);

    SF2_SPI_cs_set(spif->hnd);
    ret = SF2_SPI_transfer(spif->hnd, &command, sizeof(command), NULL, 0,
                           SPI_FLASH_TRANSFER_TIMEOUT_ms);
    SF2_SPI_cs_clear(spif->hnd);

    return ret;
}

/**
 * @brief Read SPI flash JEDEC ID.
 *
 * @param[in] spif      Pointer to an spi_flash structure.
 * @param[out] jedec_id Pointer to output data.
 *
 * @return int          SPI_FLASH_STATUS_SUCCESS or
 *                      SPI_FLASH_STATUS_TIMEOUT.
 */
static int SPI_FLASH_sf2_get_jedec(struct spi_flash *spif, u32 *jedec_id)
{
    u8 command = SPI_OPCODE_RDID;
    u8 read_buffer[6] = { 0 };
    int ret;

    K_ASSERT(spif != NULL);
    K_ASSERT(spif->hnd != NULL);
    K_ASSERT(jedec_id != NULL);

    SF2_SPI_cs_set(spif->hnd);
    ret = SF2_SPI_transfer(spif->hnd, &command, sizeof(command), read_buffer, sizeof(read_buffer),
                           SPI_FLASH_TRANSFER_TIMEOUT_ms);
    SF2_SPI_cs_clear(spif->hnd);
    if (ret)
        return ret;

    *jedec_id = (read_buffer[0] << 16) + (read_buffer[1] << 8) + read_buffer[2];
    return SPI_FLASH_STATUS_SUCCESS;
}

/**
 * @brief Verify SPI flash JEDEC ID.
 *
 * Read JEDEC ID and compare with the driver defined ID.
 *
 * Note: The driver JEDEC ID hardcoded to match the IS25LP016 SPI flash.
 *
 * @param[in] spif      Pointer to an spi_flash structure.
 *
 * @return bool         true or
 *                      false if no match.
 */
static bool SPI_FLASH_sf2_verify_jedec(struct spi_flash *spif)
{
    u32 jedec_id = 0;
    int ret;

    ret = SPI_FLASH_sf2_get_jedec(spif, &jedec_id);
    if (ret)
        return false;

    return (jedec_id == SPI_FLASH_JEDEC_ID_IS25LP016);
}

/**
 * @brief Erase SPI flash sector.
 *
 * Erase a single SPI flash sector.
 *
 * Note: Sector size is expected to be 64K bytes.
 *
 * @param[in] spif        Pointer to an spi_flash structure.
 * @param[in] addr        Address of SPI flash sector.
 * @param[in] timeout_ms  The timeout in milliseconds.
 *
 * @return int            SPI_FLASH_STATUS_SUCCESS or
 *                        SPI_FLASH_STATUS_TIMEOUT.
 */
static int SPI_FLASH_sf2_erase_64K(struct spi_flash *spif, u32 addr, u32 timeout_ms)
{
    u8 command[4];
    int ret;

    K_ASSERT(spif != NULL);
    K_ASSERT(spif->hnd != NULL);
    K_ASSERT((addr % SPI_FLASH_SECTOR_SIZE) == 0);
    K_ASSERT(timeout_ms > 0);

    ret = SPI_FLASH_sf2_write_enable(spif);
    if (ret)
        return ret;

    command[0] = SPI_OPCODE_SE;
    command[1] = (addr >> 16) & 0xFF;
    command[2] = (addr >> 8) & 0xFF;
    command[3] = addr & 0xFF;

    SF2_SPI_cs_set(spif->hnd);
    ret = SF2_SPI_transfer(spif->hnd, command, sizeof(command), NULL, 0, timeout_ms);
    if (ret)
        goto error;

    ret = SPI_FLASH_sf2_wait_ready(spif, timeout_ms);
    if (ret)
        goto error;

    SF2_SPI_cs_clear(spif->hnd);
    return SPI_FLASH_STATUS_SUCCESS;

error:
    SF2_SPI_cs_clear(spif->hnd);
    return ret;
}

/**
 * @brief Erase multiple SPI flash sectors.
 *
 * Erase multiple consecutive SPI flash sectors.
 *
 * @param[in] spif        Pointer to an spi_flash structure.
 * @param[in] addr        Address of first SPI flash sector, must be aligned on a 64 kiB boundary.
 * @param[in] num_bytes   Number of bytes to erase, will be rounded up to a multiple of 64 kiB.
 * @param[in] timeout_ms  The timeout in milliseconds.
 *
 * @return int            SPI_FLASH_STATUS_SUCCESS or
 *                        SPI_FLASH_STATUS_TIMEOUT.
 */
static int SPI_FLASH_sf2_erase_multi_64K(struct spi_flash *spif, u32 addr, u32 num_bytes, u32 timeout_ms)
{
    u32 offset;
    u32 perc_reported = 0;

    if (num_bytes > 0)
        num_bytes = round_up(num_bytes, SPI_FLASH_SECTOR_SIZE);

    for (offset = 0U; offset < num_bytes; offset += SPI_FLASH_SECTOR_SIZE) {
        u32 perc;
        int ret = SPI_FLASH_sf2_erase_64K(spif, addr + offset, timeout_ms);

        if (ret != SPI_FLASH_STATUS_SUCCESS) {
            DEBUGPRINT(3, "%s: Erasing 64K block 0x%08X - 0x%08X\n failed with %d, aborting",
                       __func__, addr, addr + offset, ret);
            return ret;
        }

        perc = (100 * (offset + SPI_FLASH_SECTOR_SIZE)) / num_bytes;
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
 * @brief Write SPI flash page.
 *
 * Note: Page size is expected to be 256 bytes.
 *
 * @param[in] spif          Pointer to an spi_flash structure.
 * @param[in] addr          Address of SPI flash page, must be aligned on a 256 byte boundary.
 * @param[in] write_buffer  Pointer to output data.
 * @param[in] num_bytes     Number of bytes to write.
 *
 * @return int              SPI_FLASH_STATUS_SUCCESS or
 *                          SPI_FLASH_STATUS_TIMEOUT.
 */
static int SPI_FLASH_sf2_write_page(struct spi_flash *spif, u32 addr, const u8 *write_buffer,
                             u32 num_bytes)
{
    u8 command[SPI_FLASH_PAGE_SIZE + 4];
    int ret;

    K_ASSERT(spif != NULL);
    K_ASSERT(spif->hnd != NULL);
    K_ASSERT((addr % SPI_FLASH_PAGE_SIZE) == 0);
    K_ASSERT(write_buffer != NULL);
    K_ASSERT(num_bytes <= SPI_FLASH_PAGE_SIZE);

    ret = SPI_FLASH_sf2_write_enable(spif);
    if (ret)
        return ret;

    command[0] = SPI_OPCODE_PP;
    command[1] = (addr >> 16) & 0xFF;
    command[2] = (addr >> 8) & 0xFF;
    command[3] = addr & 0xFF;
    memcpy(&command[4], write_buffer, num_bytes);

    SF2_SPI_cs_set(spif->hnd);
    ret =
        SF2_SPI_transfer(spif->hnd, command, 4 + num_bytes, NULL, 0, SPI_FLASH_TRANSFER_TIMEOUT_ms);
    if (ret)
        goto error;

    ret = SPI_FLASH_sf2_wait_ready(spif, SPI_FLASH_TRANSFER_TIMEOUT_ms);
    if (ret)
        goto error;

    SF2_SPI_cs_clear(spif->hnd);
    return SPI_FLASH_STATUS_SUCCESS;

error:
    SF2_SPI_cs_clear(spif->hnd);
    return ret;
}

/**
 * @brief Write multiple SPI flash pages.
 *
 * Write multiple consecutive SPI flash pages.
 *
 * @param[in] spif          Pointer to an spi_flash structure.
 * @param[in] addr          Address of SPI flash page, must be aligned on a 256 byte boundary.
 * @param[in] write_buffer  Pointer to output data.
 * @param[in] num_bytes     Number of bytes to write.
 *
 * @return int              SPI_FLASH_STATUS_SUCCESS or
 *                          SPI_FLASH_STATUS_TIMEOUT.
 */
static int SPI_FLASH_sf2_write_multi_page(struct spi_flash *spif, u32 addr, const u8 *write_buffer,
                                   u32 num_bytes)
{
    u32 offset;
    u32 perc_reported = 0;

    for (offset = 0U; offset < num_bytes; offset += SPI_FLASH_PAGE_SIZE) {
        u32 perc;
        u32 chunk_size = min(num_bytes - offset, SPI_FLASH_PAGE_SIZE);
        int ret = SPI_FLASH_sf2_write_page(spif, addr + offset, write_buffer + offset, chunk_size);

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
 * @brief Read multiple SPI flash pages.
 *
 * Read multiple consecutive SPI flash pages.
 *
 * @param[in]  spif         Pointer to an spi_flash structure.
 * @param[in]  addr         Address of SPI flash page, must be aligned on a 256 byte boundary.
 * @param[out] read_buffer  Pointer to input data.
 * @param[in]  num_bytes    Number of bytes to read.
 *
 * @return int              SPI_FLASH_STATUS_SUCCESS or
 *                          SPI_FLASH_STATUS_TIMEOUT.
 */
static int SPI_FLASH_sf2_read(struct spi_flash *spif, u32 addr, u8 *read_buffer, u32 num_bytes)
{
    u32 offset;
    u32 perc_reported = 0;
    int ret = SPI_FLASH_STATUS_TIMEOUT;

    K_ASSERT(spif != NULL);
    K_ASSERT(spif->hnd != NULL);
    K_ASSERT((addr % SPI_FLASH_PAGE_SIZE) == 0);
    K_ASSERT(read_buffer != NULL);
    K_ASSERT(num_bytes > 0);

    SF2_SPI_cs_set(spif->hnd);
    for (offset = 0U; offset < num_bytes; offset += SPI_FLASH_PAGE_SIZE) {
        u32 perc;
        u32 chunk_size = min(num_bytes - offset, SPI_FLASH_PAGE_SIZE);
        u8 command[5];

        command[0] = SPI_OPCODE_READ_FAST;
        command[1] = ((addr + offset) >> 16) & 0xFF;
        command[2] = ((addr + offset) >> 8) & 0xFF;
        command[3] = (addr + offset) & 0xFF;
        command[4] = 0; // dummy byte

        ret = SF2_SPI_transfer(spif->hnd, command, sizeof(command), read_buffer + offset,
                               chunk_size, SPI_FLASH_TRANSFER_TIMEOUT_ms);
        if (ret)
            goto error;

        perc = (100 * (offset + chunk_size)) / num_bytes;
        if ((perc - perc_reported >= PERC_STEP_READ) || (perc == 100)) {
            if (((offset == 0) && (perc == 100)) || (perc_reported == 100))
                continue;
            DEBUGPRINT(2, "Reading flash memory %3u%%\n", perc);
            perc_reported = perc;
        }
    }

    SF2_SPI_cs_clear(spif->hnd);
    return SPI_FLASH_STATUS_SUCCESS;

error:
    SF2_SPI_cs_clear(spif->hnd);
    return ret;
}

/**
 * @brief Compare SPI flash content.
 *
 * Compare SPI flash content with buffer content.
 * The comparison is done one SPI flash page at a time.
 *
 * @param[in] spif      Pointer to an spi_flash structure.
 * @param[in] addr      Address of SPI flash page, must be aligned on a 256 byte boundary.
 * @param[in] buffer    Pointer to input data.
 * @param[in] num_bytes Number of bytes to compare.
 *
 * @return int          0 if content is equal,
 *                      -1 if content mismatch, or
 *                      SPI_FLASH_STATUS_TIMEOUT.
 */
static int SPI_FLASH_sf2_compare(struct spi_flash *spif, u32 addr, const u8 *buffer, u32 num_bytes)
{
    u32 offset;
    u32 perc_reported = 0;

    for (offset = 0U; offset < num_bytes; offset += SPI_FLASH_PAGE_SIZE) {
        u32 perc;
        u32 chunk_size = min(num_bytes - offset, SPI_FLASH_PAGE_SIZE);
        u8 read_buffer[SPI_FLASH_PAGE_SIZE];
        int ret;

        ret = SPI_FLASH_sf2_read(spif, addr + offset, read_buffer, chunk_size);
        if (ret != SPI_FLASH_STATUS_SUCCESS) {
            DEBUGPRINT(2, "%s Flash page read failed with %d, aborting.", __func__, ret);
            return ret;
        }

        perc = (100 * (offset + chunk_size)) / num_bytes;
        if ((perc - perc_reported >= PERC_STEP_COMPARE) || (perc == 100)) {
            if (((offset == 0) && (perc == 100)) || (perc_reported == 100))
                continue;
            DEBUGPRINT(1, "Reading flash memory %3u%%\n", perc);
            perc_reported = perc;
        }

        if (memcmp(read_buffer, buffer + offset, chunk_size) != 0)
            return -1;
    }

    return SPI_FLASH_STATUS_SUCCESS;
}

const struct SPI_FLASH_ops SPI_FLASH_sf2_ops = {
    .init = SPI_FLASH_sf2_init,
    .deinit = SPI_FLASH_sf2_deinit,
    .start = SPI_FLASH_sf2_start,
    .stop = SPI_FLASH_sf2_stop,
    .get_status = SPI_FLASH_sf2_get_status,
    .wait_ready = SPI_FLASH_sf2_wait_ready,
    .write_enable = SPI_FLASH_sf2_write_enable,
    .write_disable = SPI_FLASH_sf2_write_disable,
    .get_jedec = SPI_FLASH_sf2_get_jedec,
    .verify_jedec = SPI_FLASH_sf2_verify_jedec,
    .erase_64K = SPI_FLASH_sf2_erase_64K,
    .erase_multi_64K = SPI_FLASH_sf2_erase_multi_64K,
    .write_page = SPI_FLASH_sf2_write_page,
    .write_multi_page = SPI_FLASH_sf2_write_multi_page,
    .read = SPI_FLASH_sf2_read,
    .compare = SPI_FLASH_sf2_compare,
};

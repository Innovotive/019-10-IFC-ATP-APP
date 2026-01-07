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
 * Kvaser generic SPI flash implementation
 *
 * @note: This module is NOT thread safe, only perform
 *        one ongoing operation at any time!
 */

#include "k_assert.h"
#include "spi_flash.h"

#define ASSERT_SPIF(spif) \
    do {                                \
        K_ASSERT(spif != NULL);                 \
        K_ASSERT(spif->ops != NULL);            \
    } while (0)

/**
 * @brief Set operations struct and initialize and configure SPI comm.
 *
 * @param spif       Pointer to spi_flash struct
 * @param base_addr  Pointer to the SPI IOMEM block
 *
 * @return int       SPI_FLASH_STATUS_SUCCESS or error code != 0
 */
int SPI_FLASH_init(struct spi_flash *spif,
                   const struct SPI_FLASH_ops *spi_ops,
                   void __iomem *base_addr)
{
    K_ASSERT(spif != NULL);
    K_ASSERT(spi_ops != NULL);

    spif->ops = spi_ops;
    return spif->ops->init(spif, base_addr);
}

/**
 * @brief Deinitialize SPI comm.
 *
 * @param spif  Pointer to spi_flash struct
 */
void SPI_FLASH_deinit(struct spi_flash *spif)
{

    ASSERT_SPIF(spif);
    spif->ops->deinit(spif);
}

/**
 * Start the SPI driver so that interrupts and the device are enabled.
 *
 * @param spif       Pointer to spi_flash struct
 *
 * @return int       SPI_FLASH_STATUS_SUCCESS or error code != 0
 */
int SPI_FLASH_start(struct spi_flash *spif)
{
    ASSERT_SPIF(spif);
    return spif->ops->start(spif);
}

/**
 * Stop the SPI driver.
 *
 * @param spif       Pointer to spi_flash struct
 *
 * @return int       SPI_FLASH_STATUS_SUCCESS or error code != 0
 */
int SPI_FLASH_stop(struct spi_flash *spif)
{
    ASSERT_SPIF(spif);
    return spif->ops->stop(spif);
}

/**
 * This function reads the status register of the Flash.
 *
 * @param spif       Pointer to spi_flash struct
 * @param status     Pointer to the read status.
 *
 * @return int       SPI_FLASH_STATUS_SUCCESS or error code != 0
 */
int SPI_FLASH_get_status(struct spi_flash *spif, u8 *status)
{
    ASSERT_SPIF(spif);
    return spif->ops->get_status(spif, status);
}

/**
 * @brief Wait until the serial flash is ready to accept a command
 *
 * @param spif       Pointer to spi_flash struct
 * @param timeout_ms Timeout in ms
 *
 * @return int       SPI_FLASH_STATUS_SUCCESS or error code != 0
 */
int SPI_FLASH_wait_ready(struct spi_flash *spif, u32 timeout_ms)
{
    ASSERT_SPIF(spif);
    return spif->ops->wait_ready(spif, timeout_ms);
}

/**
 * @brief Enable writes to the serial flash memory.
 *
 * @param spif       Pointer to spi_flash struct
 *
 * @return int       SPI_FLASH_STATUS_SUCCESS or error code != 0
 */
int SPI_FLASH_write_enable(struct spi_flash *spif)
{
    ASSERT_SPIF(spif);
    return spif->ops->write_enable(spif);
}

/**
 * @brief Disable writes to the serial flash memory.
 *
 * @param spif       Pointer to spi_flash struct
 *
 * @return int       SPI_FLASH_STATUS_SUCCESS or error code != 0
 */
int SPI_FLASH_write_disable(struct spi_flash *spif)
{
    ASSERT_SPIF(spif);
    return spif->ops->write_disable(spif);
}

/**
 * @brief Get JEDEC id
 *
 * @param spif       Pointer to spi_flash struct
 * @param jedec      JEDEC id
 *
 * @return           SPI_FLASH_STATUS_SUCCESS or error code != 0
 */
int SPI_FLASH_get_jedec(struct spi_flash *spif, u32 *jedec)
{
    ASSERT_SPIF(spif);
    return spif->ops->get_jedec(spif, jedec);
}

/**
 * @brief Verify flash JEDEC id
 *
 * @param spif       Pointer to spi_flash struct
 *
 * @return true      If expected JEDEC id
 * @return false     If read fails or unexpected JEDEC id
 */
bool SPI_FLASH_verify_jedec(struct spi_flash *spif)
{
    ASSERT_SPIF(spif);
    return spif->ops->verify_jedec(spif);
}

/**
 * @brief Erase a 64 kiB block
 *
 * @param spif       Pointer to spi_flash struct
 * @param addr       Start address of block
 * @param timeout_ms Timeout in ms
 *
 * @return int       SPI_FLASH_STATUS_SUCCESS or error code != 0
 *
 */
int SPI_FLASH_erase_64K(struct spi_flash *spif, u32 addr, u32 timeout_ms)
{
    ASSERT_SPIF(spif);
    return spif->ops->erase_64K(spif, addr, timeout_ms);
}

/**
 * @brief Erase one or more 64 kiB blocks
 *
 * @param spif       Pointer to spi_flash struct
 * @param addr       Start address of block
 * @param num_bytes  Total number of bytes to erase. Must be a multiple
 *                   of 64 kiB and > 0.
 * @param timeout_ms Timeout in ms
 *
 * @return int       SPI_FLASH_STATUS_SUCCESS or error code != 0
 */
int SPI_FLASH_erase_multi_64K(struct spi_flash *spif, u32 addr, u32 num_bytes, u32 timeout_ms)
{
    ASSERT_SPIF(spif);
    return spif->ops->erase_multi_64K(spif, addr, num_bytes, timeout_ms);
}

/**
 * @brief Write up to 256 bytes of data to a specified location in the serial flash memory.
 *
 * @param spif       Pointer to spi_flash struct
 * @param addr       Start address in flash to write to, must be aligned on a 256 byte boundary.
 * @param buf        Pointer to buffer containing data to write
 * @param num_bytes  The number of bytes to be written (<= 256)
 *
 * @return int       SPI_FLASH_STATUS_SUCCESS or error code != 0
 */
int SPI_FLASH_write_page(struct spi_flash *spif, u32 addr, const u8 *buf, u32 num_bytes)
{
    ASSERT_SPIF(spif);
    return spif->ops->write_page(spif, addr, buf, num_bytes);
}

/**
 * @brief Write multiple pages of up to 256 bytes of data to a specified
 *        location in the serial flash memory.
 *
 * @param spif       Pointer to spi_flash struct
 * @param addr       Start address in flash to write to, must be aligned on a 256 byte boundary.
 * @param buf        Pointer to buffer containing data to write
 * @param num_bytes  The number of bytes to be written (<= 256)
 *
 * @return int       SPI_FLASH_STATUS_SUCCESS or error code != 0
 */
int SPI_FLASH_write_multi_page(struct spi_flash *spif, u32 addr, const u8 *buf, u32 num_bytes)
{
    ASSERT_SPIF(spif);
    return spif->ops->write_multi_page(spif, addr, buf, num_bytes);
}

/**
 * @brief Read multiple pages of up to 256 bytes of data from a
 *        specified location in the serial flash memory.
 *
 * @param spif       Pointer to spi_flash struct
 * @param addr       Start address in flash to read from, must be aligned on a 256 byte boundary.
 * @param buf        Pointer to buffer to read data into
 * @param num_bytes  The number of bytes to be read
 *
 * @return int       SPI_FLASH_STATUS_SUCCESS or error code != 0
 */
int SPI_FLASH_read(struct spi_flash *spif, u32 addr, u8 *buf, u32 num_bytes)
{
    ASSERT_SPIF(spif);
    return spif->ops->read(spif, addr, buf, num_bytes);
}

/**
 * @brief Compare the contents of a buffer with the contents of a
 *        specified location in the serial flash memory.
 *
 * @param spif       Pointer to spi_flash struct
 * @param addr       Start address in flash to read from, must be aligned on a 256 byte boundary.
 * @param buf        Pointer to buffer containing data to compare with flash contents
 * @param num_bytes  The number of bytes to compare
 *
 * @return int       If buffers are equal: SPI_FLASH_STATUS_SUCCESS
 *                   If buffers are not equal: -1
 *                   If error: error code > 0
 */
int SPI_FLASH_compare(struct spi_flash *spif, u32 addr, const u8 *buf, u32 num_bytes)
{
    ASSERT_SPIF(spif);
    return spif->ops->compare(spif, addr, buf, num_bytes);
}

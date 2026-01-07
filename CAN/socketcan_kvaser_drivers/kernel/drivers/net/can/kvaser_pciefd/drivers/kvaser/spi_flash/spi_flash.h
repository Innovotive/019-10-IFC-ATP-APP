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

#ifndef __SPI_FLASH_H__
#define __SPI_FLASH_H__

#include <linux/types.h>
#ifdef __KERNEL__
#include <linux/wait.h>
#else
#include <time.h>
#include <stdbool.h>
#include "user_kernel.h"
#endif /* __KERNEL__ */
#include "util.h"
#include "timespec.h"

/**
 * Generic low level driver for SPI flash memories
 *
 * @note: This module is NOT thread safe, only perform
 *        one ongoing operation at any time!
 */

#define SPI_FLASH_STATUS_SUCCESS 0
#define SPI_FLASH_STATUS_MALLOC  1
#define SPI_FLASH_STATUS_TIMEOUT 2

struct spi_flash {
    void *hnd;  // Must be the first struct member!
    const struct SPI_FLASH_ops *ops;
    timespec_t time;
    bool dry_run;
};

int SPI_FLASH_init(struct spi_flash *spif,
                   const struct SPI_FLASH_ops *spi_ops,
                   void __iomem *base_addr);
void SPI_FLASH_deinit(struct spi_flash *spif);
int SPI_FLASH_start(struct spi_flash *spif);
int SPI_FLASH_stop(struct spi_flash *spif);
int SPI_FLASH_get_status(struct spi_flash *spif, u8 *status);
int SPI_FLASH_wait_ready(struct spi_flash *spif, u32 timeout_ms);
int SPI_FLASH_write_enable(struct spi_flash *spif);
int SPI_FLASH_write_disable(struct spi_flash *spif);
int SPI_FLASH_get_jedec(struct spi_flash *spif, u32 *jedec);
bool SPI_FLASH_verify_jedec(struct spi_flash *spif);
int SPI_FLASH_erase_64K(struct spi_flash *spif, u32 addr, u32 timeout_ms);
int SPI_FLASH_erase_multi_64K(struct spi_flash *spif, u32 addr, u32 num_bytes, u32 timeout_ms);
int SPI_FLASH_write_page(struct spi_flash *spif, u32 addr, const u8 *buf, u32 num_bytes);
int SPI_FLASH_write_multi_page(struct spi_flash *spif, u32 addr, const u8 *buf, u32 num_bytes);
int SPI_FLASH_read(struct spi_flash *spif, u32 addr, u8 *buf, u32 num_bytes);
int SPI_FLASH_compare(struct spi_flash *spif, u32 addr, const u8 *buf, u32 num_bytes);

struct SPI_FLASH_ops {
    int (*init)(struct spi_flash *spif, void __iomem *base_addr);
    void (*deinit)(struct spi_flash *spif);
    int (*start)(struct spi_flash *spif);
    int (*stop)(struct spi_flash *spif);
    int (*get_status)(struct spi_flash *spif, u8 *status);
    int (*wait_ready)(struct spi_flash *spif, u32 timeout_ms);
    int (*write_enable)(struct spi_flash *spif);
    int (*write_disable)(struct spi_flash *spif);
    int (*get_jedec)(struct spi_flash *spif, u32 *jedec);
    bool (*verify_jedec)(struct spi_flash *spif);
    int (*erase_64K)(struct spi_flash *spif, u32 addr, u32 timeout_ms);
    int (*erase_multi_64K)(struct spi_flash *spif, u32 addr, u32 num_bytes, u32 timeout_ms);
    int (*write_page)(struct spi_flash *spif, u32 addr, const u8 *buf, u32 num_bytes);
    int (*write_multi_page)(struct spi_flash *spif, u32 addr, const u8 *buf, u32 num_bytes);
    int (*read)(struct spi_flash *spif, u32 addr, u8 *buf, u32 num_bytes);
    int (*compare)(struct spi_flash *spif, u32 addr, const u8 *buf, u32 num_bytes);
};

extern const struct SPI_FLASH_ops SPI_FLASH_altera_ops;
extern const struct SPI_FLASH_ops SPI_FLASH_sf2_ops;
extern const struct SPI_FLASH_ops SPI_FLASH_xilinx_ops;
extern const struct SPI_FLASH_ops SPI_FLASH_dummy_ops;
#endif // __SPI_FLASH_H__

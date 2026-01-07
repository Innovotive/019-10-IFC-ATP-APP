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
 * \brief SPI driver for Microchip M2S025
 *
 * Current limitations:
 *  - SPI controller 0 only
 *  - Hardcoded SPI chip select to slave 0
 *  - SPI master only
 *  - Standard SPI (Motorola) only, not the SSP (Texas Instruments) or
 *    MICROWIRE (National Semiconductor) protocol variants
 *  - The same SPI mode and clock speed are used for all slaves
 *  - Hardcoded SPI mode and SPI clock speed
 *  - No support for interrupts or DMA transfer
 *  - No checking or handling of RX overflow, since it should not happen
 *
 * Implementation details:
 *  - The SPI transfer is implemented as a busy loop.
 *  - The SPI transfer will first transmit and then receive (no simultaneous
 *    transmit and receive)
 */

#ifndef SF2_SPI_H_
#define SF2_SPI_H_

#include <linux/types.h>
#ifndef __KERNEL__
#include "user_kernel.h"
#endif /* NOT __KERNEL__ */

/** @brief Return value indicating a successful result. */
#define SF2_SPI_STATUS_SUCCESS 0

/** @brief Return value indicating that a timeout occurred. */
#define SF2_SPI_STATUS_TIMEOUT 1

/** @brief Maximum number of bytes per SPI transfer. */
#define SF2_SPI_MAX_TRANSFER_BYTES (0xFFFF)

/**
 * @brief SF2 SPI data structure.
 *
 * Note: The contents are private to the driver.
 */
struct SF2_SPI {
    void __iomem *base;
    u32 clk_div;
    u8 frame_width;
    u8 fifo_depth;
};

/**
 * @brief Initialize the SPI0 controller.
 *
 * The SPI controller is set up as a master, with all of the following fixed:
 * - transfer protocol (Motorola SPI)
 * - SPI mode (SPO = 1, SPH = 1, SPS = 1)
 * - clock divider (configurable in sf2_spi.c)
 * - frame width (configurable in sf2_spi.c)
 *
 * Note: The System Register Block is also expected to be accessible through
 *       the same memory map as the SPI0 registers.
 *
 * @param[in,out] spi   Pointer to an SF2 SPI structure.
 * @param[in] base      Base address of the SPI0 registers.
 */
void SF2_SPI_init(struct SF2_SPI *spi, void __iomem *base);

/**
 * @brief Select an SPI slave.
 *
 * @param[in] spi    Pointer to an SF2 SPI structure.
 */
void SF2_SPI_cs_set(struct SF2_SPI *spi);

/**
 * @brief Deselect an SPI slave.
 *
 * @param[in] spi    Pointer to an SF2 SPI structure.
 */
void SF2_SPI_cs_clear(struct SF2_SPI *spi);

/**
 * @brief Perform a bidirectional SPI transfer, with timeout.
 *
 * The transfer is performed in a busy loop, by first transmitting all the
 * \a write_buffer_size bytes from the \a write_buffer, and then receiving
 * \a read_buffer_size bytes and saving them to the \a read_buffer.
 * Thus, the total SPI transfer size is the sum of the two buffer sizes.
 *
 * If a timeout occurs, no cleaning up is done, so it is probably best to
 * reinitialize the controller if it is expected to be used again.
 *
 * @param[in]  spi                  Pointer to an SF2 SPI structure.
 * @param[in]  write_buffer         Pointer to output data.
 * @param[in]  write_buffer_size    Output data size.
 * @param[out] read_buffer          Pointer to input data.
 * @param[in]  read_buffer_size     Input data size.
 * @param[in]  timeout_ms           The timeout in milliseconds.
 *
 * @return int                      SPI_FLASH_STATUS_SUCCESS or
 *                                  SPI_FLASH_STATUS_TIMEOUT
 */
int SF2_SPI_transfer(struct SF2_SPI *spi, const u8 *write_buffer, u32 write_buffer_size,
                     u8 *read_buffer, u32 read_buffer_size, u32 timeout_ms);

#endif /* SF2_SPI_H_*/


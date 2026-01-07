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
#include <linux/version.h>
#if LINUX_VERSION_CODE < KERNEL_VERSION(4, 19, 0)
#include <linux/bitops.h>
#else
#include <linux/bits.h>
#endif /* LINUX_VERSION_CODE < 4.19 */
#include <linux/io.h>
#include <linux/types.h>

#if LINUX_VERSION_CODE < KERNEL_VERSION(3, 13, 0)
#define GENMASK(h, l) (((U32_C(1) << ((h) - (l) + 1)) - 1) << (l))
#endif /* LINUX_VERSION_CODE < 3.13 */
#endif /* __KERNEL__ */
#include "k_assert.h"
#include "debugprint.h"
#include "util.h"
#include "timespec.h"
#include "sf2_spi.h"

/* Configuration. */

/** SPI slave select. */
#define SPI_SLAVE   BIT(0)
/** Data frame width, in number of bits. */
#define FRAME_WIDTH (8)
/** SPI clock divider. Must be 2n, for n in [1, 256]. */
#define SPI_CLK_DIV (8)

/* SPI register offsets. */

/** SPI Control Register offset. */
#define SF2_SPI_CONTROL      (0x00)
/** SPI TxRx Data Frame Register offset. */
#define SF2_SPI_TXRXDF_SIZE  (0x04)
/** SPI Status Register offset. */
#define SF2_SPI_STATUS       (0x08)
/** SPI Interrupt Clear Register offset. */
#define SF2_SPI_INT_CLEAR    (0x0C)
/** SPI Receive Data Register offset. */
#define SF2_SPI_RX_DATA      (0x10)
/** SPI Transmit Data Register offset. */
#define SF2_SPI_TX_DATA      (0x14)
/** SPI SCLK Generation Register offset. */
#define SF2_SPI_CLK_GEN      (0x18)
/** SPI Slave Select Register offset. */
#define SF2_SPI_SLAVE_SELECT (0x1C)
/** SPI Masked Interrupt Status Register offset. */
#define SF2_SPI_MIS          (0x20)
/** SPI Raw Interrupt Status Register offset. */
#define SF2_SPI_RIS          (0x24)
/** SPI Control2 Register offset. */
#define SF2_SPI_CONTROL2     (0x28)
/** SPI Command Register offset. */
#define SF2_SPI_COMMAND      (0x2C)
/** SPI Packet Size Register offset. */
#define SF2_SPI_PKTSIZE      (0x30)
/** SPI Command Size Register offset. */
#define SF2_SPI_CMD_SIZE     (0x34)
/** SPI Hardware Status Register offset. */
#define SF2_SPI_HWSTATUS     (0x38)

/* SPI register contents. */

#define SF2_SPI_CONTROL_ENABLE           BIT(0)
#define SF2_SPI_CONTROL_MODE             BIT(1)
#define SF2_SPI_CONTROL_TRANSFPRTL       GENMASK(3, 2)
#define SF2_SPI_CONTROL_INTRXDATA        BIT(4)
#define SF2_SPI_CONTROL_INTTXDATA        BIT(5)
#define SF2_SPI_CONTROL_INTRXOVRFLO      BIT(6)
#define SF2_SPI_CONTROL_INTTXTURUN       BIT(7)
#define SF2_SPI_CONTROL_TXRXDFCOUNT_MASK GENMASK(23, 8)
#define SF2_SPI_CONTROL_SPO              BIT(24)
#define SF2_SPI_CONTROL_SPH              BIT(25)
#define SF2_SPI_CONTROL_SPS              BIT(26)
#define SF2_SPI_CONTROL_FRAMEURUN        BIT(27)
#define SF2_SPI_CONTROL_CLKMODE          BIT(28)
#define SF2_SPI_CONTROL_BIGFIFO          BIT(29)
#define SF2_SPI_CONTROL_OENOFF           BIT(30)
#define SF2_SPI_CONTROL_RESET            BIT(31)

#define SF2_SPI_CONTROL_TRANSFPRTL_SPI       (0x0 * BIT(2))
#define SF2_SPI_CONTROL_TRANSFPRTL_SSP       (0x1 * BIT(2))
#define SF2_SPI_CONTROL_TRANSFPRTL_MICROWIRE (0x2 * BIT(2))
#define SF2_SPI_CONTROL_TXRXDFCOUNT_BASE     BIT(8)

#define SF2_SPI_TXRXDF_SIZE_TXRXDFS_MASK GENMASK(5, 0)

#define SF2_SPI_STATUS_TXDATSENT    BIT(0)
#define SF2_SPI_STATUS_RXDATRCED    BIT(1)
#define SF2_SPI_STATUS_RXOVERFLOW   BIT(2)
#define SF2_SPI_STATUS_TXUNDERRUN   BIT(3)
#define SF2_SPI_STATUS_RXFIFOFUL    BIT(4)
#define SF2_SPI_STATUS_RXFIFOFULNXT BIT(5)
#define SF2_SPI_STATUS_RXFIFOEMP    BIT(6)
#define SF2_SPI_STATUS_RXFIFOEMPNXT BIT(7)
#define SF2_SPI_STATUS_TXFIFOFUL    BIT(8)
#define SF2_SPI_STATUS_TXFIFOFULNXT BIT(9)
#define SF2_SPI_STATUS_TXFIFOEMP    BIT(10)
#define SF2_SPI_STATUS_TXFIFOEMPNXT BIT(11)
#define SF2_SPI_STATUS_FRAMESTART   BIT(12)
#define SF2_SPI_STATUS_SSEL         BIT(13)
#define SF2_SPI_STATUS_ACTIVE       BIT(14)

#define SF2_SPI_STATUS_FIFOS_EMPTY (SF2_SPI_STATUS_RXFIFOEMP | SF2_SPI_STATUS_TXFIFOEMP)

#define SF2_SPI_CLK_GEN_CLK_GEN_MASK GENMASK(7, 0)

#define SF2_SPI_SLAVE_SELECT_SLAVESELECT_MASK GENMASK(7, 0)

#define SF2_SPI_COMMAND_AUTOFILL    BIT(0)
#define SF2_SPI_COMMAND_AUTOEMPTY   BIT(1)
#define SF2_SPI_COMMAND_RXFIFORST   BIT(2)
#define SF2_SPI_COMMAND_TXFIFORST   BIT(3)
#define SF2_SPI_COMMAND_CLRFRAMECNT BIT(4)
#define SF2_SPI_COMMAND_AUTOSTALL   BIT(5)
#define SF2_SPI_COMMAND_TXNOW       BIT(6)

/**
 * @brief SYSREG Software Reset Control Register offset.
 *
 * This register is in the System Register Block, and is used to handle the
 * software reset of the SPI controller.
 *
 * Note: the register offset is relative to the SPI0 base address, since
 * that is the only one this driver gets to know.
 */
#define SF2_SYSREG_SOFT_RESET_CR (0x37000 + 0x48)

#define SF2_SYSREG_SOFT_RESET_CR_SPI0_SOFTRESET BIT(9)

/* Internal function(s). */

/**
 * @brief Update a 32-bit register value.
 *
 * Updates a 32-bit register value, by first clearing a specified set of bits,
 * and then setting another specified set of bits.
 *
 * @param addr      Pointer to the register.
 * @param clear     Bits to clear.
 * @param set       Bits to set.
 */
static inline void update_reg(void __iomem *addr, u32 clear, u32 set)
{
    iowrite32(((ioread32(addr) & ~clear) | set), addr);
}

/**
 * @brief Clear bits of a 32-bit register.
 *
 * Updates a 32-bit register value, by clearing a specified set of bits.
 *
 * @param addr      Pointer to the register.
 * @param clear     Bits to clear.
 */
static inline void clear_reg(void __iomem *addr, u32 clear)
{
    update_reg(addr, clear, 0);
}

/**
 * @brief Set bits of a 32-bit register.
 *
 * Updates a 32-bit register value, by setting a specified set of bits.
 *
 * @param addr      Pointer to the register.
 * @param set       Bits to set.
 */
static inline void set_reg(void __iomem *addr, u32 set)
{
    update_reg(addr, 0, set);
}

/* Interface functions. Documented in sf2_spi.h. */

void SF2_SPI_init(struct SF2_SPI *spi, void __iomem *base)
{
    K_ASSERT(spi != NULL);
    K_ASSERT(base != NULL);

    spi->base = base;
    spi->clk_div = SPI_CLK_DIV;
    spi->frame_width = FRAME_WIDTH;
    spi->fifo_depth = ((spi->frame_width <= 4)  ? 32 :
                       (spi->frame_width <= 8)  ? 16 :
                       (spi->frame_width <= 16) ? 8 :
                                                  4);

    /* Do a software reset of the controller. */
    set_reg(spi->base + SF2_SYSREG_SOFT_RESET_CR, SF2_SYSREG_SOFT_RESET_CR_SPI0_SOFTRESET);
    clear_reg(spi->base + SF2_SYSREG_SOFT_RESET_CR, SF2_SYSREG_SOFT_RESET_CR_SPI0_SOFTRESET);

    update_reg(spi->base + SF2_SPI_CONTROL,
               (SF2_SPI_CONTROL_ENABLE | SF2_SPI_CONTROL_TRANSFPRTL | SF2_SPI_CONTROL_RESET),
               (SF2_SPI_CONTROL_MODE | SF2_SPI_CONTROL_TRANSFPRTL_SPI | SF2_SPI_CONTROL_SPO |
                SF2_SPI_CONTROL_SPH | SF2_SPI_CONTROL_SPS | SF2_SPI_CONTROL_BIGFIFO |
                SF2_SPI_CONTROL_CLKMODE));

    update_reg(spi->base + SF2_SPI_CLK_GEN, SF2_SPI_CLK_GEN_CLK_GEN_MASK, ((spi->clk_div / 2) - 1));

    update_reg(spi->base + SF2_SPI_TXRXDF_SIZE, SF2_SPI_TXRXDF_SIZE_TXRXDFS_MASK, spi->frame_width);

    clear_reg(spi->base + SF2_SPI_SLAVE_SELECT, SF2_SPI_SLAVE_SELECT_SLAVESELECT_MASK);

    set_reg(spi->base + SF2_SPI_CONTROL, SF2_SPI_CONTROL_ENABLE);
}

void SF2_SPI_cs_set(struct SF2_SPI *spi)
{
    K_ASSERT(spi != NULL);

    set_reg(spi->base + SF2_SPI_SLAVE_SELECT, SPI_SLAVE);
}

void SF2_SPI_cs_clear(struct SF2_SPI *spi)
{
    K_ASSERT(spi != NULL);

    clear_reg(spi->base + SF2_SPI_SLAVE_SELECT, SPI_SLAVE);
}

int SF2_SPI_transfer(struct SF2_SPI *spi, const u8 *write_buffer, u32 write_buffer_size,
                     u8 *read_buffer, u32 read_buffer_size, u32 timeout_ms)
{
    u32 transfer_size;
    u32 transmitted;
    u32 received;
    u32 outstanding;
    timespec_t timeout;

    K_ASSERT(spi != NULL);
    if (write_buffer_size != 0)
        K_ASSERT(write_buffer != NULL);
    if (read_buffer_size != 0)
        K_ASSERT(read_buffer != NULL);

    TIMESPEC_GET(timeout);
    TIMESPEC_ADD_MSEC(timeout, timeout_ms);

    transfer_size = write_buffer_size + read_buffer_size;

    K_ASSERT(transfer_size <= SF2_SPI_MAX_TRANSFER_BYTES);

    set_reg(spi->base + SF2_SPI_COMMAND, (SF2_SPI_COMMAND_RXFIFORST | SF2_SPI_COMMAND_TXFIFORST));

    update_reg(spi->base + SF2_SPI_CONTROL, SF2_SPI_CONTROL_TXRXDFCOUNT_MASK,
               (SF2_SPI_CONTROL_TXRXDFCOUNT_BASE * (transfer_size & SF2_SPI_MAX_TRANSFER_BYTES)));

    K_ASSERT((ioread32(spi->base + SF2_SPI_STATUS) & SF2_SPI_STATUS_FIFOS_EMPTY) ==
             SF2_SPI_STATUS_FIFOS_EMPTY);

    received = transmitted = outstanding = 0;

    while (received < transfer_size) {
        u8 val;

        if (TIMESPEC_IS_AFTER_EQ(timeout))
            goto timeout;

        while ((transmitted < transfer_size) && (outstanding < spi->fifo_depth)) {
            val = ((transmitted < write_buffer_size) ? *(write_buffer++) : 0);
            iowrite32((u32)val, (spi->base + SF2_SPI_TX_DATA));
            ++outstanding;
            ++transmitted;
        }

        while (outstanding) {
            if (ioread32(spi->base + SF2_SPI_STATUS) & SF2_SPI_STATUS_RXFIFOEMP)
                break;
            val = (u8)ioread32(spi->base + SF2_SPI_RX_DATA);
            --outstanding;
            ++received;
            if (received > write_buffer_size)
                *(read_buffer++) = val;
        }
    }
    return SF2_SPI_STATUS_SUCCESS;

timeout:
    DEBUGPRINT(1, "%s: timed out, leaving\n", __func__);
    return SF2_SPI_STATUS_TIMEOUT;
}


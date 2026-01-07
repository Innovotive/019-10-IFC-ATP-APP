/******************************************************************************
* Copyright (C) 2012 - 2020 Xilinx, Inc.  All rights reserved.
* SPDX-License-Identifier: MIT
******************************************************************************/

/**
 * Low level driver for the IS25LP032 32 MB SPI flash
 * developed by Kvaser AB based on xspi_winbond_flash_quad_example.c
 *
 * @note: This module is NOT thread safe, only perform
 *        one ongoing operation at any time!
 */

/***************************** Include Files *********************************/
#ifdef __KERNEL__
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wtype-limits"
#include <linux/wait.h>
#pragma GCC diagnostic pop
#include <linux/sched.h>
#include <linux/delay.h>
#include <linux/slab.h>
#include <linux/string.h>
#else
#include <stddef.h>
#include <stdint.h>
#include <string.h> /* memcpy */
#endif /* __KERNEL__ */
#include "k_assert.h"
#include "util.h"
#include "debugprint.h"
#include "xspi.h"
#include "spi_flash.h"

/************************** Constant Definitions *****************************/
#define SIMULATE_WRITE 0

#if SIMULATE_WRITE
#pragma message __FILE__ " is compiled in write simulation mode."
#endif

#define JEDEC_IS25LP032 0x009D6016

/* Progress in % logged during flash operations */
#define PERC_STEP_READ    20
#define PERC_STEP_WRITE   20
#define PERC_STEP_ERASE   20
#define PERC_STEP_COMPARE 20

/*
 * Number of bytes per page in the flash device.
 */
#define FLASH_PAGE_SIZE 256U

#define QUAD_MODE 1 // Use quad mode

/*
 * The following constant defines the slave select signal that is used to
 * to select the Flash device on the SPI bus, this signal is typically
 * connected to the chip select of the device.
 */
#define SPI_SELECT 0x01

/**
 * Definition of commands
 *
 * Note: FRQDTR, SER and BER32 does not work with the IS25LP032
 */
#define CMD_READ_NORMAL   0x03 /* Normal read (NORD) */
#define CMD_READ_FAST     0x0B /* Fast read (FRD) */
#define CMD_READ_QUAD     0xEB /* Fast read quad IO (FRQIO) */
#define CMD_READ_QUAD_DTR 0xED /* Fast read quad IO DTR (FRQDTR) */

#define CMD_WRITE_PAGE      0x02 /* Input page program (PP) */
#define CMD_WRITE_PAGE_QUAD 0x32 /* Quad Input Fast Program (PPQ)*/

#define CMD_WRITE_ENABLE  0x06 /* Write enable (WREN) */
#define CMD_WRITE_DISABLE 0x04 /* Write disable (WRDI) */

#define CMD_ERASE_4K   0xD7 /* 4K sector erase (SER) */
#define CMD_ERASE_32K  0x52 /* 32 K block erase (BER32) */
#define CMD_ERASE_64K  0xD8 /* 64 K block erase (BER64) */
#define CMD_ERASE_CHIP 0xC7 /* Chip erase (CER) */

#define CMD_STATUSREG_READ    0x05 /* Read status register (RDSR) */
#define CMD_READ_JEDEC_ID_SPI 0x9F /* Read JEDEC id in SPI mode*/

/**
 * These definitions specify the EXTRA bytes in each of the command
 * transactions. This count includes command byte, address bytes and any
 * don't care bytes needed.
 */
#define EXTRA_READ_WRITE    4U /* Read/Write extra bytes */
#define EXTRA_WRITE_ENABLE  1U /* Write enable extra bytes */
#define EXTRA_PARTIAL_ERASE 4U /* Block erase extra bytes */
#define EXTRA_BULK_ERASE    1U /* Bulk erase extra bytes */
#define EXTRA_STATUS_READ   2U /* status read extra bytes */
#define EXTRA_STATUS_WRITE  2U /* status write extra bytes */
#define EXTRA_JEDEC_ID      4U

/*
 * Flash not busy mask in the status register of the flash device.
 */
#define FLASH_SR_IS_READY_MASK 0x01 /* Ready mask */

/*
 * The following definitions specify the number of dummy bytes to ignore in the
 * data read from the flash, through various Read commands. This is apart from
 * the dummy bytes returned in response to the command and address transmitted.
 */
/*
 * After transmitting Dual Read command and address on DIO0,the quad spi device
 * configures DIO0 and DIO1 in input mode and receives data on both DIO0 and
 * DIO1 for 8 dummy clock cycles. So we end up with 16 dummy bits in DRR. The
 * same logic applies Quad read command, so we end up with 4 dummy bytes in
 * that case.
 */
#define DUMMY_BYTES_DUAL_READ    2U
#define DUMMY_BYTES_QUAD_READ    4U
#define DUMMY_BYTES_DUAL_IO_READ 2U
#define DUMMY_BYTES_QUAD_IO_READ 3U // 5 in Xilinx example, 6 in data sheet !

static_assert(SPI_FLASH_STATUS_SUCCESS == XST_SUCCESS);

/**************************** Type Definitions *******************************/

/***************** Macros (Inline Functions) Definitions *********************/
#define XSPI(spif) (spif->hnd)

/************************** Function Prototypes ******************************/

/************************** Variable Definitions *****************************/

/************************** Function Definitions *****************************/

/**
* Initialize and prepare handle
*
* @param spif       Pointer to spi_flash struct
* @param base_addr  is a pointer to the AXI SPI block
* @return int       SPI_FLASH_STATUS_SUCCESS or error code != 0
*/
static int SPI_FLASH_xilinx_init(struct spi_flash *spif, void *base_addr)
{
    int status;
    XSpi_Config config = {
        .HasFifos = TRUE,
        .SlaveOnly = FALSE,
        .NumSlaveBits = 1,
        .DataWidth = XSP_DATAWIDTH_BYTE,
        .SpiMode = (QUAD_MODE ? XSP_QUAD_MODE : XSP_STANDARD_MODE),
        .XipMode = FALSE,
        .Use_Startup = TRUE,
    };

    K_ASSERT(spif != NULL);
    K_ASSERT(base_addr != NULL);

    spif->hnd = kzalloc(sizeof(XSpi), GFP_KERNEL);
    if (spif->hnd == NULL)
        return SPI_FLASH_STATUS_MALLOC;

    status = XSpi_CfgInitialize(XSPI(spif), &config, (UINTPTR)base_addr);
    if (status != XST_SUCCESS)
        goto error_exit;

    /*
     * Set the SPI device as a master and in manual slave select mode such
     * that the slave select signal does not toggle for every byte of a
     * transfer, this must be done before the slave select is set.
     */
    status = XSpi_SetOptions(XSPI(spif), XSP_MASTER_OPTION | XSP_MANUAL_SSELECT_OPTION);
    if (status != XST_SUCCESS)
        goto error_exit;

    /*
     * Select the flash device on the SPI bus, so that it can be
     * read and written using the SPI bus.
     */
    status = XSpi_SetSlaveSelect(XSPI(spif), SPI_SELECT);
    if (status != XST_SUCCESS)
        goto error_exit;

    return SPI_FLASH_STATUS_SUCCESS;

error_exit:
    if (spif->hnd != NULL) {
        kfree(spif->hnd);
        spif->hnd = NULL;
    }
    return status;
}

/**
* @brief Deinitialize the SPI controller.
*
* @param spif       Pointer to spi_flash struct
*/
static void SPI_FLASH_xilinx_deinit(struct spi_flash *spif)
{
    K_ASSERT(spif != NULL);

    if (spif->hnd != NULL) {
        kfree(spif->hnd);
        spif->hnd = NULL;
    }
}

/**
* Start the SPI driver so that interrupts and the device are enabled.
*
* @param spif   Pointer to spi_flash struct
* @return int   XST_SUCCESS if successful or XST_DEVICE_IS_STARTED if the
*               device was already started.
*/
static int SPI_FLASH_xilinx_start(struct spi_flash *spif)
{
    int status;

    K_ASSERT(spif != NULL);
    K_ASSERT(XSPI(spif) != NULL);

    status = XSpi_Start(XSPI(spif));

    // Disable global interrupt in order to use polled mode
    XSpi_IntrGlobalDisable((XSpi *)XSPI(spif));

    return status;
}

/**
* Shut down
*
* @param spif    Pointer to spi_flash struct
* @return int    XST_SUCCESS if the device is successfully stopped.
*                XST_DEVICE_BUSY if a transfer is in progress and cannot be
*                stopped.
*/
static int SPI_FLASH_xilinx_stop(struct spi_flash *spif)
{
    K_ASSERT(spif != NULL);
    K_ASSERT(XSPI(spif) != NULL);

    return XSpi_Stop(XSPI(spif));
}

/**
* This function reads the status register of the Flash.
*
* @param spif   Pointer to spi_flash struct
* @param result Pointer to the read status.
* @return int   SPI_FLASH_STATUS_SUCCESS or error code != 0
*/
static int SPI_FLASH_xilinx_get_status(struct spi_flash *spif, u8 *result)
{
    u8 buf[EXTRA_STATUS_READ] = { 0 };
    int status;

    K_ASSERT(spif != NULL);
    K_ASSERT(XSPI(spif) != NULL);
    K_ASSERT(result != NULL);

    buf[0] = CMD_STATUSREG_READ;

    status = XSpi_Transfer(XSPI(spif), buf, buf, EXTRA_STATUS_READ);
    if (status != XST_SUCCESS) {
        DEBUGPRINT(3, "%s: Transfer failed with %i\n", __func__, status);
        return status;
    }

    *result = buf[1];
    DEBUGPRINT(10, "%s: status 0x%02X\n", __func__, *result);
    return SPI_FLASH_STATUS_SUCCESS;
}

/**
* Wait until the serial flash is ready to accept next command.
*
* @param spif       Pointer to spi_flash struct
* @param timeout_ms If > 0 Max waiting time in ms
* @return int       SPI_FLASH_STATUS_SUCCESS or error code != 0
*
* @note This function reads the status register and waits
*       until the WIP bit of the status register becomes 0.
*/
static int SPI_FLASH_xilinx_wait_ready(struct spi_flash *spif, u32 timeout_ms)
{
    timespec_t timeout;
    int status;
    u8 status_reg;

    K_ASSERT(spif != NULL);
    K_ASSERT(XSPI(spif) != NULL);

    TIMESPEC_GET(timeout);
    TIMESPEC_ADD_MSEC(timeout, timeout_ms);

    do {
        status = SPI_FLASH_xilinx_get_status(spif, &status_reg);

        if (status != XST_SUCCESS) {
            DEBUGPRINT(3, "%s: SPI_FLASH_xilinx_get_status failed!\n", __func__);
            return status;
        }

        if ((status_reg & FLASH_SR_IS_READY_MASK) == 0)
            return SPI_FLASH_STATUS_SUCCESS;

        MSLEEP_SHORT(5);

    } while (TIMESPEC_IS_BEFORE(timeout));

    DEBUGPRINT(3, "%s: Timeout after %u ms!\n", __func__, timeout_ms);
    return XST_FAILURE;
}

/**
* Send a one byte command to the serial flash memory.
*
* @param spif   Pointer to spi_flash struct
* @param cmd    The command to send
*
* @return int   SPI_FLASH_STATUS_SUCCESS or error code != 0
*/
static int send_one_byte_cmd(struct spi_flash *spif, u8 cmd)
{
    u8 buf[1];
    int status;

    K_ASSERT(spif != NULL);
    K_ASSERT(XSPI(spif) != NULL);

    buf[0] = cmd;

    status = SPI_FLASH_xilinx_wait_ready(spif, 100);
    if (status != XST_SUCCESS)
        return status;

    status = XSpi_Transfer(XSPI(spif), buf, NULL, 1);
    if (status != XST_SUCCESS)
        return status;

    return SPI_FLASH_STATUS_SUCCESS;
}

/**
* Enable writes to the serial flash memory.
*
* @param spif   Pointer to spi_flash struct
* @return int   SPI_FLASH_STATUS_SUCCESS or error code != 0
*/
static int SPI_FLASH_xilinx_write_enable(struct spi_flash *spif)
{
    return send_one_byte_cmd(spif, CMD_WRITE_ENABLE);
}

/**
* Disable writes to the serial flash memory.
*
* @param spif   Pointer to spi_flash struct
* @return int   SPI_FLASH_STATUS_SUCCESS or error code != 0
*/
static int SPI_FLASH_xilinx_write_disable(struct spi_flash *spif)
{
    return send_one_byte_cmd(spif, CMD_WRITE_DISABLE);
}

/**
 * Get JEDEC id
 *
 * @param spif  Pointer to spi_flash struct
 * @param jedec JEDEC id
 * @return int  SPI_FLASH_STATUS_SUCCESS or error code != 0
 */
static int SPI_FLASH_xilinx_get_jedec(struct spi_flash *spif, u32 *jedec)
{
    u8 buf[EXTRA_JEDEC_ID] = { 0 };
    int status;

    K_ASSERT(spif != NULL);
    K_ASSERT(XSPI(spif) != NULL);
    K_ASSERT(jedec != NULL);

    buf[0] = CMD_READ_JEDEC_ID_SPI;

    status = SPI_FLASH_xilinx_wait_ready(spif, 100);
    if (status != XST_SUCCESS)
        return status;

    status = XSpi_Transfer(XSPI(spif), buf, buf, EXTRA_JEDEC_ID);
    if (status != XST_SUCCESS)
        return status;

    *jedec = (buf[1] << 16) + (buf[2] << 8) + buf[3];
    return SPI_FLASH_STATUS_SUCCESS;
}

/**
 * Verify flash JEDEC id
 *
 * @param spif  Pointer to spi_flash struct
 * @return bool True if expected JEDEC id, false otherwise
 */
static bool SPI_FLASH_xilinx_verify_jedec(struct spi_flash *spif)
{
    int status;
    u32 jedec;

    status = SPI_FLASH_xilinx_get_jedec(spif, &jedec);
    if (status != XST_SUCCESS)
        return false;

    DEBUGPRINT(3, "JEDEC id = 0x%08X", jedec);
    return (jedec == JEDEC_IS25LP032);
}

/**
* Erase the contents of the specified memory section in the
* serial flash device using a specified method.
*
* @param spif       Pointer to spi_flash struct
* @param addr       The address within a 64 k block which is to
*                   be erased.
* @param cmd        CMD_4K_ERASE || CMD_ERASE_64K || CMD_ERASE_CHIP
* @param timeout_ms if > 0 this function will wait this long for the
*                   erase operation to finish or return XST_FLASH_TIMEOUT_ERROR
* @return int       SPI_FLASH_STATUS_SUCCESS or error code != 0
*/
#if !SIMULATE_WRITE
static int flash_erase_cmd(struct spi_flash *spif, u32 addr, u8 cmd, u32 timeout_ms)
{
    u8 buf[EXTRA_PARTIAL_ERASE] = { 0 };
    int status;

    K_ASSERT(spif != NULL);
    K_ASSERT(XSPI(spif) != NULL);
    K_ASSERT((cmd == CMD_ERASE_4K) || (cmd == CMD_ERASE_32K) || (cmd == CMD_ERASE_64K) ||
               (cmd == CMD_ERASE_CHIP));

    buf[0] = cmd;
    if (cmd != CMD_ERASE_CHIP) {
        buf[1] = (u8)(addr >> 16);
        buf[2] = (u8)(addr >> 8);
        buf[3] = (u8)(addr);
    }

    status = SPI_FLASH_xilinx_wait_ready(spif, 100);
    if (status != XST_SUCCESS)
        return status;

    status = SPI_FLASH_xilinx_write_enable(spif);
    if (status != XST_SUCCESS)
        return status;

    status = XSpi_Transfer(XSPI(spif), buf, NULL,
                           (cmd == CMD_ERASE_CHIP) ? EXTRA_BULK_ERASE : EXTRA_PARTIAL_ERASE);
    if (status != XST_SUCCESS)
        return status;

    if (timeout_ms > 0) {
        status = SPI_FLASH_xilinx_wait_ready(spif, timeout_ms);
        if (status != XST_SUCCESS)
            return XST_FLASH_TIMEOUT_ERROR;
    }

    return SPI_FLASH_STATUS_SUCCESS;
}
#endif

/**
* Erase a 64K block
*
* @param spif       Pointer to spi_flash struct
* @param addr       The address within a 64k block which is to
*                   be erased.
* @param timeout_ms if > 0 this function will wait this long for the
*                   erase operation to finish or return XST_FLASH_TIMEOUT_ERROR
* @return int       SPI_FLASH_STATUS_SUCCESS or error code != 0
*
* @note 64K erase is the smallest working erase command.
*/
static int SPI_FLASH_xilinx_erase_64K(struct spi_flash *spif, u32 addr, u32 timeout_ms)
{
    K_ASSERT((addr % (64 * 1024U)) == 0);

#if !SIMULATE_WRITE
    DEBUGPRINT(8, "%s: Erasing 64K block 0x%08X - 0x%08X\n", __func__, addr, addr + (64 * 1024));
    return flash_erase_cmd(spif, addr, CMD_ERASE_64K, timeout_ms);
#else
    NOT_USED(spif);
    NOT_USED(timeout_ms);

    DEBUGPRINT(8, "%s: Simulating erase of 64K block 0x%08X - 0x%08X\n", __func__, addr,
               addr + (64 * 1024));
    return SPI_FLASH_STATUS_SUCCESS;
#endif
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
static int SPI_FLASH_xilinx_erase_multi_64K(struct spi_flash *spif, u32 addr, u32 num_bytes,
                                     u32 timeout_ms)
{
    const u32 chunk_size = 64 * 1024U;
    const u32 loop_sleep_ms = 1;
    u32 offset;
    u32 perc_reported = 0;

    if (num_bytes > 0)
        num_bytes = round_up(num_bytes, chunk_size);

    for (offset = 0U; offset < num_bytes; offset += chunk_size) {
        u32 perc;
        int status;

        status = SPI_FLASH_xilinx_erase_64K(spif, addr + offset, timeout_ms);
        if (status != XST_SUCCESS) {
            DEBUGPRINT(3, "%s: Erasing 64K block 0x%08X - 0x%08X\n failed with %d, aborting",
                       __func__, addr, addr + offset, status);
            return status;
        }

        perc = (100 * (offset + chunk_size)) / num_bytes;
        if ((perc - perc_reported >= PERC_STEP_ERASE) || (perc == 100)) {
            if (((offset == 0) && (perc == 100)) || (perc_reported == 100))
                continue;
            DEBUGPRINT(1, "%s flash memory %3u%%\n",
                       SIMULATE_WRITE ? "Simulating erase of" : "Erasing", perc);
            perc_reported = perc;
        }

        MSLEEP_SHORT(loop_sleep_ms);
    }

    return SPI_FLASH_STATUS_SUCCESS;
}

/**
* Write up to 256 bytes of data to a specified location
* in the serial flash memory.
*
* @param spif       Pointer to spi_flash struct
* @param addr       The address in the flash memory, where to write the data.
*                   It must be aligned on a 256 byte boundary.
* @param buf        The pointer to a buffer containing up to 256 bytes to be
*                   written to the flash memory.
* @param num_bytes  The number of bytes to be written (<= 256)
*
* @return int       SPI_FLASH_STATUS_SUCCESS or error code != 0
*/
static int SPI_FLASH_xilinx_write_page(struct spi_flash *spif, u32 addr, const u8 *buf, u32 num_bytes)
{
    u8 tx_buf[FLASH_PAGE_SIZE + EXTRA_READ_WRITE];
    int status;

    K_ASSERT(spif != NULL);
    K_ASSERT(XSPI(spif) != NULL);
    K_ASSERT(0 == (addr % FLASH_PAGE_SIZE));
    K_ASSERT(buf != NULL);
    K_ASSERT(num_bytes <= FLASH_PAGE_SIZE);

#if !SIMULATE_WRITE
    DEBUGPRINT(8, "%s: Writing %u bytes at 0x%08X - 0x%08X\n", __func__, num_bytes, addr,
               addr + num_bytes);

    tx_buf[0] = (QUAD_MODE ? CMD_WRITE_PAGE_QUAD : CMD_WRITE_PAGE);
    tx_buf[1] = (u8)(addr >> 16);
    tx_buf[2] = (u8)(addr >> 8);
    tx_buf[3] = (u8)addr;
    memcpy(&tx_buf[4], buf, num_bytes);

    status = SPI_FLASH_xilinx_wait_ready(spif, 100);
    if (status != XST_SUCCESS)
        return status;

    status = SPI_FLASH_xilinx_write_enable(spif);
    if (status != XST_SUCCESS)
        return status;

    status = XSpi_Transfer(XSPI(spif), tx_buf, NULL, (num_bytes + EXTRA_READ_WRITE));
    if (status != XST_SUCCESS)
        return status;

    return SPI_FLASH_STATUS_SUCCESS;
#else
    NOT_USED(tx_buf);
    NOT_USED(status);
    NOT_USED(timeout_ms);
    DEBUGPRINT(8, "%s: Simulating write of %u bytes at 0x%08X - 0x%08X\n", __func__, num_bytes,
               addr, addr + num_bytes);
    return SPI_FLASH_STATUS_SUCCESS;
#endif
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
static int SPI_FLASH_xilinx_write_multi_page(struct spi_flash *spif, u32 addr, const u8 *buf,
                                      u32 num_bytes)
{
    const u32 loop_sleep_ms = 1;
    u32 offset;
    u32 perc_reported = 0;

    for (offset = 0U; offset < num_bytes; offset += FLASH_PAGE_SIZE) {
        u32 perc;
        u32 chunk_size = min(num_bytes - offset, FLASH_PAGE_SIZE);
        int status;

        status = SPI_FLASH_xilinx_write_page(spif, addr + offset, buf + offset, chunk_size);
        if (status != XST_SUCCESS) {
            DEBUGPRINT(2, "%s Error, page write failed with %d, aborting.", __func__, status);
            return status;
        }

        perc = (100 * (offset + chunk_size)) / num_bytes;
        if ((perc - perc_reported >= PERC_STEP_WRITE) || (perc == 100)) {
            if (((offset == 0) && (perc == 100)) || (perc_reported == 100))
                continue;
            DEBUGPRINT(1, "%s flash memory %3u%%\n",
                       SIMULATE_WRITE ? "Simulating write of" : "Writing", perc);
            perc_reported = perc;
        }

        MSLEEP_SHORT(loop_sleep_ms);
    }

    return SPI_FLASH_STATUS_SUCCESS;
}

/**
* Read up to a page size (256 bytes) of data from a specified location in the serial flash memory.
*
* @param spif       Pointer to spi_flash struct
* @param addr       The starting address in the flash memory from which the
*                   data is to be read. Will wrap if flash size is exceeded.
* @param buf        The pointer to a buffer in which the data read from the
*                   flash memory will be stored. Size must be >= num_bytes.
* @param num_bytes  The number of bytes to be read, must be <= 256!
*
* @return int       SPI_FLASH_STATUS_SUCCESS or error code != 0
*
*/
static int SPI_FLASH_xilinx_read_page(struct spi_flash *spif, u32 addr, u8 *buf, u32 num_bytes)
{
    const u32 num_extra_bytes = EXTRA_READ_WRITE + (QUAD_MODE ? DUMMY_BYTES_QUAD_IO_READ : 0);
    u8 rw_buf[FLASH_PAGE_SIZE + EXTRA_READ_WRITE + DUMMY_BYTES_QUAD_IO_READ] = { 0 };
    u32 total_num_bytes;
    int status;

    K_ASSERT(spif != NULL);
    K_ASSERT(XSPI(spif) != NULL);
    K_ASSERT(buf != NULL);
    K_ASSERT(num_bytes <= FLASH_PAGE_SIZE);

    DEBUGPRINT(8, "%s: Reading %u bytes at 0x%08X - 0x%08X\n", __func__, num_bytes, addr,
               addr + num_bytes);

    total_num_bytes = num_bytes + num_extra_bytes;
    rw_buf[0] = CMD_READ_QUAD;
    rw_buf[1] = (u8)(addr >> 16);
    rw_buf[2] = (u8)(addr >> 8);
    rw_buf[3] = (u8)addr;

    status = SPI_FLASH_xilinx_wait_ready(spif, 100);
    if (status != XST_SUCCESS)
        return status;

    status = XSpi_Transfer(XSPI(spif), rw_buf, rw_buf, total_num_bytes);
    if (status != XST_SUCCESS)
        return status;

    // return requested data only
    memcpy(buf, rw_buf + num_extra_bytes, num_bytes);
    return SPI_FLASH_STATUS_SUCCESS;
}

/**
* Read multiple pages of up to 256 bytes of data from a
* specified location in the serial flash memory.
*
* @param spif       Pointer to spi_flash struct
* @param addr       The starting address in the Flash Memory from which the
*                   data is to be read. Will wrap if flash size is exceeded.
* @param buf        The pointer to a buffer in which the data read from the
*                   flash memory will be stored. Size must be >= num_bytes.
* @param num_bytes  The number of bytes to be read
*
* @return int       SPI_FLASH_STATUS_SUCCESS or error code != 0
*/
static int SPI_FLASH_xilinx_read(struct spi_flash *spif, u32 addr, u8 *buf, u32 num_bytes)
{
    const u32 loop_sleep_ms = 1;
    u32 offset;
    u32 perc_reported = 0;

    for (offset = 0U; offset < num_bytes; offset += FLASH_PAGE_SIZE) {
        u32 perc;
        u32 chunk_size = min(num_bytes - offset, FLASH_PAGE_SIZE);
        int status;

        status = SPI_FLASH_xilinx_read_page(spif, addr + offset, buf + offset, chunk_size);
        if (status != XST_SUCCESS) {
            DEBUGPRINT(2, "%s Flash page read failed with %d, aborting.", __func__, status);
            return status;
        }

        perc = (100 * (offset + chunk_size)) / num_bytes;
        if ((perc - perc_reported >= PERC_STEP_READ) || (perc == 100)) {
            if (((offset == 0) && (perc == 100)) || (perc_reported == 100))
                continue;
            DEBUGPRINT(2, "Reading flash memory %3u%%\n", perc);
            perc_reported = perc;
        }

        MSLEEP_SHORT(loop_sleep_ms);
    }

    return SPI_FLASH_STATUS_SUCCESS;
}

/**
* Compare the contents of a buffer with the contents of a
* specified location in the serial flash memory.
*
* @param spif       Pointer to spi_flash struct
* @param addr       The starting address in the flash memory from which the
*                   data is to be read. Will wrap if flash size is exceeded.
* @param buf        Pointer to buffer containing data to compare with flash contents.
* @param num_bytes  The number of bytes to compare
*
* @return           If buffers are equal: SPI_FLASH_STATUS_SUCCESS
*                   If buffers are not equal: -1
*                   If error: error code > 0
*/
static int SPI_FLASH_xilinx_compare(struct spi_flash *spif, u32 addr, const u8 *buf, u32 num_bytes)
{
    const u32 loop_sleep_ms = 1;
    u32 offset;
    u32 perc_reported = 0;

    for (offset = 0U; offset < num_bytes; offset += FLASH_PAGE_SIZE) {
        u32 perc;
        u32 remaining = num_bytes - offset;
        u32 chunk_size = min(remaining, FLASH_PAGE_SIZE);
        u8 page_buf[FLASH_PAGE_SIZE];
        int status;

        status = SPI_FLASH_xilinx_read_page(spif, addr + offset, page_buf, chunk_size);
        if (status != XST_SUCCESS) {
            DEBUGPRINT(2, "%s Flash page read failed with %d, aborting.", __func__, status);
            return status;
        }

        perc = (100 * (offset + chunk_size)) / num_bytes;
        if ((perc - perc_reported >= PERC_STEP_COMPARE) || (perc == 100)) {
            if (((offset == 0) && (perc == 100)) || (perc_reported == 100))
                continue;
            DEBUGPRINT(1, "Reading flash memory %3u%%\n", perc);
            perc_reported = perc;
        }

        if (memcmp(page_buf, buf + offset, chunk_size) != 0)
            return -1;

        MSLEEP_SHORT(loop_sleep_ms);
    }

    return SPI_FLASH_STATUS_SUCCESS;
}

const struct SPI_FLASH_ops SPI_FLASH_xilinx_ops = {
    .init = SPI_FLASH_xilinx_init,
    .deinit = SPI_FLASH_xilinx_deinit,
    .start = SPI_FLASH_xilinx_start,
    .stop = SPI_FLASH_xilinx_stop,
    .get_status = SPI_FLASH_xilinx_get_status,
    .wait_ready = SPI_FLASH_xilinx_wait_ready,
    .write_enable = SPI_FLASH_xilinx_write_enable,
    .write_disable = SPI_FLASH_xilinx_write_disable,
    .get_jedec = SPI_FLASH_xilinx_get_jedec,
    .verify_jedec = SPI_FLASH_xilinx_verify_jedec,
    .erase_64K = SPI_FLASH_xilinx_erase_64K,
    .erase_multi_64K = SPI_FLASH_xilinx_erase_multi_64K,
    .write_page = SPI_FLASH_xilinx_write_page,
    .write_multi_page = SPI_FLASH_xilinx_write_multi_page,
    .read = SPI_FLASH_xilinx_read,
    .compare = SPI_FLASH_xilinx_compare,
};

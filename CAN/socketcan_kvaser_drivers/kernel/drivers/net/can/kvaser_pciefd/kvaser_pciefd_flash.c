// SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause
/* Copyright (C) 2025 KVASER AB, Sweden. All rights reserved.
 */

#include <linux/types.h>

#include "hydra_flash.h"
#include "kvaser_pciefd.h"
#include "spi_flash.h"

#include "kvaser_pciefd_flash.h"

const struct hydra_flash_image_def flash_meta_altera = {
	.size = (2 * 1024 * 1024U), /* 2MiB */
	.fpga_image_offset = 0U,
	.fpga_image_size_max = 0x1f0000,
	.param_image_offset = 0x1f0000,
	.param_image_size_max = (64 * 1024U), /* 64 KiB (partially used */
};

const struct kvaser_pciefd_flash_data KVASER_PCIEFD_FLASH_DATA_ALTERA = {
	.spi_offset = 0x1f800,
	.flash_meta = &flash_meta_altera,
	.spi_ops = &SPI_FLASH_altera_ops,
};

const struct hydra_flash_image_def flash_meta_sf2 = {
	.size = (2 * 1024 * 1024U), /* 2MiB */
	.fpga_image_offset = 0U,
	.fpga_image_size_max = 0x1f0000,
	.param_image_offset = 0x1f0000,
	.param_image_size_max = (64 * 1024U), /* 64 KiB (partially used */
};

const struct kvaser_pciefd_flash_data KVASER_PCIEFD_FLASH_DATA_SF2 = {
	.spi_offset = 0x1000,
	.flash_meta = &flash_meta_sf2,
	.spi_ops = &SPI_FLASH_sf2_ops,
};

const struct hydra_flash_image_def flash_meta_xilinx = {
	.size = (4 * 1024 * 1024U), /* 4MiB */
	.fpga_image_offset = 0U,
	.fpga_image_size_max = 0x3f0000,
	.param_image_offset = 0x3f0000,
	.param_image_size_max = (64 * 1024U), /* 64 KiB (partially used */
};

const struct kvaser_pciefd_flash_data KVASER_PCIEFD_FLASH_DATA_XILINX = {
	.spi_offset = 0x1000,
	.flash_meta = &flash_meta_xilinx,
	.spi_ops = &SPI_FLASH_xilinx_ops,
};

int kvaser_pciefd_read_flash_params(struct kvaser_pciefd *pcie)
{
	struct hydra_flash_ctx hflash = {0};
	const struct kvaser_pciefd_flash_data *flash_data = pcie->driver_data->flash_data;
	void __iomem *spi_base = pcie->reg_base + flash_data->spi_offset;
	int ret;

	/* Initialize SPI */
	ret = SPI_FLASH_init(&hflash.spif, flash_data->spi_ops, spi_base);
	if (ret)
		return ret;

	ret = SPI_FLASH_start(&hflash.spif);
	if (ret)
		return ret;

	ret = HYDRA_FLASH_init(&hflash, flash_data->flash_meta, NULL, NULL);
	if (ret)
		return ret;

	/* Verify SPI flash JEDEC ID */
	if(!SPI_FLASH_verify_jedec(&hflash.spif))
		return -ENODEV;

	ret = HYDRA_FLASH_read_params(&hflash);
	if (ret)
		return ret;

	pcie->ean[1] = hflash.params.ean >> 32;
	pcie->ean[0] = hflash.params.ean & 0xffffffff;
	pcie->serial_number = hflash.params.serial_number;
	pcie->hw_revision = hflash.params.hw_rev_major;

	return ret;
}

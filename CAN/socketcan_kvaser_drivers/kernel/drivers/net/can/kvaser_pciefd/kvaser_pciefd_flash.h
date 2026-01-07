// SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause
/* kvaser_pciefd flash definitions and declarations
 *
 * Copyright (C) 2025 KVASER AB, Sweden. All rights reserved.
 */
#ifndef _KVASER_PCIEFD_FLASH_H
#define _KVASER_PCIEFD_FLASH_H

#include "hydra_flash.h"
#include "spi_flash.h"

struct kvaser_pciefd_flash_data {
	const u32 spi_offset;
	const struct hydra_flash_image_def *flash_meta;
	const struct SPI_FLASH_ops *spi_ops;
};

extern const struct kvaser_pciefd_flash_data KVASER_PCIEFD_FLASH_DATA_XILINX;
extern const struct kvaser_pciefd_flash_data KVASER_PCIEFD_FLASH_DATA_SF2;
extern const struct kvaser_pciefd_flash_data KVASER_PCIEFD_FLASH_DATA_ALTERA;
#endif /* _KVASER_PCIEFD_FLASH_H */

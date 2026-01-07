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
#ifndef _HYDRA_FLASH_H
#define _HYDRA_FLASH_H

#ifndef __KERNEL__
#include <stdbool.h>
#include "user_kernel.h"
#endif /* NOT __KERNEL__ */
#include "kcan_ioctl_flash.h"
#include "spi_flash.h"

#define HYDRA_FLASH_PARAM_MAX_SIZE    24
#define HYDRA_FLASH_MAX_CARD_CHANNELS 8

#define HYDRA_FLASH_STAT_OK            0
#define HYDRA_FLASH_STAT_FAIL          -1
#define HYDRA_FLASH_STAT_TIMEOUT       -2
#define HYDRA_FLASH_STAT_NO_MEMORY     -5
#define HYDRA_FLASH_STAT_BAD_PARAMETER -7

typedef uint8_t cust_channel_name_t[HYDRA_FLASH_PARAM_MAX_SIZE];

struct hydra_flash_parameters {
    uint64_t ean;
    uint32_t serial_number;
    uint32_t max_bitrate;
    uint8_t nr_channels;
    uint8_t hw_rev_major;
    uint8_t hw_type;
    uint8_t trans_type[HYDRA_FLASH_MAX_CARD_CHANNELS];
    cust_channel_name_t cust_channel_name[HYDRA_FLASH_MAX_CARD_CHANNELS];
};

struct hydra_flash_device_ops {
    int (*firmware_upgrade_trigger_update)(void *data);
    void (*display_update_state)(void *data, bool update_active);
};

// flash image constants
struct hydra_flash_image_def {
    u32 size;
    u32 param_image_size_max;
    u32 param_image_offset;
    u32 fpga_image_size_max;
    u32 fpga_image_offset;
};

struct hydra_flash_ctx {
    struct spi_flash spif;
    const struct hydra_flash_image_def *image_def;
    const struct hydra_flash_device_ops *device_ops;
    struct hydra_flash_parameters params;
    uint8_t *flash_image;
    void *data;
};

int HYDRA_FLASH_init(struct hydra_flash_ctx *ctx,
                     const struct hydra_flash_image_def *img_def,
                     const struct hydra_flash_device_ops *dev_ops,
                     void *data);
void HYDRA_FLASH_deinit(struct hydra_flash_ctx *ctx);
int HYDRA_FLASH_read_params(struct hydra_flash_ctx *ctx);
int HYDRA_FLASH_update_fw_ioctl(struct hydra_flash_ctx *ctx, KCAN_FLASH_PROG *fp);

#endif /* _HYDRA_FLASH_H */

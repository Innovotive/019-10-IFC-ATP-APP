# SPDX-License-Identifier: GPL-2.0-only
obj-$(CONFIG_CAN_KVASER_PCIEFD) += kvaser_pciefd.o
kvaser_pciefd-y = kvaser_pciefd_core.o kvaser_pciefd_devlink.o \
                  kvaser_pciefd_flash.o \
                  drivers/kvaser/spi_flash/spi_flash_xilinx.o \
                  drivers/kvaser/spi_flash/spi_flash.o \
                  drivers/kvaser/spi_flash/spi_flash_sf2.o \
                  drivers/kvaser/spi_flash/spi_flash_altera.o \
                  drivers/altera/HAL/src/altera_avalon_epcs_flash_controller.o \
                  drivers/altera/HAL/src/altera_avalon_spi.o \
                  drivers/altera/HAL/src/epcs_commands.o \
                  drivers/kvaser/hydra_flash/hydra_flash.o \
                  drivers/kvaser/spi/sf2_spi/sf2_spi.o \
                  drivers/xilinx/spi/src/xspi.o \
                  drivers/xilinx/spi/src/xspi_options.o

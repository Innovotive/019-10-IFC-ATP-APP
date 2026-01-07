// SPDX-License-Identifier: GPL-2.0
/* kvaser_pciefd devlink functions
 *
 * Copyright (C) 2025 KVASER AB, Sweden. All rights reserved.
 */

#include <linux/netdevice.h>
#include <net/devlink.h>
#include <linux/version.h>

#include "kvaser_pciefd.h"

#define KVASER_USB_EAN_MSB 0x00073301

#if ((LINUX_VERSION_CODE >= KERNEL_VERSION(5, 0, 0)) && IS_ENABLED(CONFIG_NET_DEVLINK)) || KV_FORCE_DEVLINK
static int kvaser_pciefd_devlink_info_get(struct devlink *devlink,
					  struct devlink_info_req *req,
					  struct netlink_ext_ack *extack)
{
	struct kvaser_pciefd *pcie = devlink_priv(devlink);
	char buf[16]; /* 73301XXXXXXXXXX */
	int ret;

	if (pcie->fw_version.major) {
		snprintf(buf, sizeof(buf), "%u.%u.%u",
			 pcie->fw_version.major,
			 pcie->fw_version.minor,
			 pcie->fw_version.build);
		ret = devlink_info_version_running_put(req,
						       DEVLINK_INFO_VERSION_GENERIC_FW,
						       buf);
		if (ret)
			return ret;
	}

	if (pcie->serial_number) {
		snprintf(buf, sizeof(buf), "%u", pcie->serial_number);
		ret = devlink_info_serial_number_put(req, buf);
		if (ret)
			return ret;
	}

	if (pcie->hw_revision) {
		snprintf(buf, sizeof(buf), "%u", pcie->hw_revision);
		ret = devlink_info_version_fixed_put(req,
						     DEVLINK_INFO_VERSION_GENERIC_BOARD_REV,
						     buf);
		if (ret)
			return ret;
	}

	if (pcie->ean[1] == KVASER_USB_EAN_MSB) {
		snprintf(buf, sizeof(buf), "%x%08x", pcie->ean[1], pcie->ean[0]);
		ret = devlink_info_version_fixed_put(req,
						     DEVLINK_INFO_VERSION_GENERIC_BOARD_ID,
						     buf);
		if (ret)
			return ret;
	}

	return 0;
}

const struct devlink_ops kvaser_pciefd_devlink_ops = {
	.info_get = kvaser_pciefd_devlink_info_get,
};

int kvaser_pciefd_devlink_port_register(struct kvaser_pciefd_can *can)
{
	int ret;
#if (LINUX_VERSION_CODE >= KERNEL_VERSION(5, 9, 0))
	struct devlink_port_attrs attrs = {
		.flavour = DEVLINK_PORT_FLAVOUR_PHYSICAL,
		.phys.port_number = can->can.dev->dev_id,
	};
	devlink_port_attrs_set(&can->devlink_port, &attrs);
#else
	devlink_port_attrs_set(&can->devlink_port, DEVLINK_PORT_FLAVOUR_PHYSICAL,
			       can->can.dev->dev_id, false, 0, NULL, 0);
#endif /* LINUX_VERSION_CODE >= KERNEL_VERSION 5.9.0 */

	ret = devlink_port_register(priv_to_devlink(can->kv_pcie),
				    &can->devlink_port, can->can.dev->dev_id);
	if (ret)
		return ret;

#if (LINUX_VERSION_CODE >= KERNEL_VERSION(6, 2, 0))
	SET_NETDEV_DEVLINK_PORT(can->can.dev, &can->devlink_port);
#else
	devlink_port_type_eth_set(&can->devlink_port, can->can.dev);
#endif /* LINUX_VERSION_CODE >= KERNEL_VERSION 6.2.0 */

	return 0;
}

void kvaser_pciefd_devlink_port_unregister(struct kvaser_pciefd_can *can)
{
	devlink_port_unregister(&can->devlink_port);
}
#else
#pragma message "For devlink support, the kernel must be built with CONFIG_NET_DEVLINK and run version 5.0 or later!"
const struct devlink_ops kvaser_usb_devlink_ops = {};

int kvaser_pciefd_devlink_port_register(struct kvaser_pciefd_can *can)
{
	return 0;
}

void kvaser_pciefd_devlink_port_unregister(struct kvaser_pciefd_can *can)
{
}
#endif /* (LINUX_VERSION_CODE >= KERNEL_VERSION 5.0.0 && IS_ENABLED(CONFIG_NET_DEVLINK)) || KV_FORCE_DEVLINK */

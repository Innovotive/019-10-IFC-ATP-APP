// SPDX-License-Identifier: GPL-2.0
/* kvaser_usb devlink functions
 *
 * Copyright (C) 2025 KVASER AB, Sweden. All rights reserved.
 */

#include <linux/netdevice.h>
#include <net/devlink.h>
#include <linux/version.h>

#include "kvaser_usb.h"

#define KVASER_USB_EAN_MSB 0x00073301

#if ((LINUX_VERSION_CODE >= KERNEL_VERSION(5, 0, 0)) && IS_ENABLED(CONFIG_NET_DEVLINK)) || KV_FORCE_DEVLINK
static int kvaser_usb_devlink_info_get(struct devlink *devlink,
				       struct devlink_info_req *req,
				       struct netlink_ext_ack *extack)
{
	struct kvaser_usb *dev = devlink_priv(devlink);
	char buf[16]; /* 73301XXXXXXXXXX */
	int ret;

	if (dev->serial_number) {
		snprintf(buf, sizeof(buf), "%u", dev->serial_number);
		ret = devlink_info_serial_number_put(req, buf);
		if (ret)
			return ret;
	}

	if (dev->fw_version.major) {
		snprintf(buf, sizeof(buf), "%u.%u.%u",
			 dev->fw_version.major,
			 dev->fw_version.minor,
			 dev->fw_version.revision);
		ret = devlink_info_version_running_put(req,
						       DEVLINK_INFO_VERSION_GENERIC_FW,
						       buf);
		if (ret)
			return ret;
	}

	if (dev->hw_revision) {
		snprintf(buf, sizeof(buf), "%u", dev->hw_revision);
		ret = devlink_info_version_fixed_put(req,
						     DEVLINK_INFO_VERSION_GENERIC_BOARD_REV,
						     buf);
		if (ret)
			return ret;
	}

	if (dev->ean[1] == KVASER_USB_EAN_MSB) {
		snprintf(buf, sizeof(buf), "%x%08x", dev->ean[1], dev->ean[0]);
		ret = devlink_info_version_fixed_put(req,
						     DEVLINK_INFO_VERSION_GENERIC_BOARD_ID,
						     buf);
		if (ret)
			return ret;
	}

	return 0;
}

const struct devlink_ops kvaser_usb_devlink_ops = {
	.info_get = kvaser_usb_devlink_info_get,
};

int kvaser_usb_devlink_port_register(struct kvaser_usb_net_priv *priv)
{
	int ret;
#if (LINUX_VERSION_CODE >= KERNEL_VERSION(5, 9, 0))
	struct devlink_port_attrs attrs = {
		.flavour = DEVLINK_PORT_FLAVOUR_PHYSICAL,
		.phys.port_number = priv->channel,
	};
	devlink_port_attrs_set(&priv->devlink_port, &attrs);
#else
	devlink_port_attrs_set(&priv->devlink_port, DEVLINK_PORT_FLAVOUR_PHYSICAL,
			       priv->channel, false, 0, NULL, 0);
#endif /* LINUX_VERSION_CODE >= KERNEL_VERSION 5.9.0 */

	ret = devlink_port_register(priv_to_devlink(priv->dev),
				    &priv->devlink_port, priv->channel);
	if (ret)
		return ret;

#if (LINUX_VERSION_CODE >= KERNEL_VERSION(6, 2, 0))
	SET_NETDEV_DEVLINK_PORT(priv->netdev, &priv->devlink_port);
#endif /* LINUX_VERSION_CODE >= KERNEL_VERSION 6.2.0 */

	return 0;
}

void kvaser_usb_devlink_port_unregister(struct kvaser_usb_net_priv *priv)
{
	devlink_port_unregister(&priv->devlink_port);
}
#else
#pragma message "For devlink support, the kernel must be built with CONFIG_NET_DEVLINK and run version 5.0 or later!"
const struct devlink_ops kvaser_usb_devlink_ops = {};

int kvaser_usb_devlink_port_register(struct kvaser_usb_net_priv *priv)
{
	return 0;
}

void kvaser_usb_devlink_port_unregister(struct kvaser_usb_net_priv *priv)
{
}
#endif /* (LINUX_VERSION_CODE >= KERNEL_VERSION 5.0.0 && IS_ENABLED(CONFIG_NET_DEVLINK)) || KV_FORCE_DEVLINK */

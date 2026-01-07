#include <linux/module.h>
#include <linux/export-internal.h>
#include <linux/compiler.h>

MODULE_INFO(name, KBUILD_MODNAME);

__visible struct module __this_module
__section(".gnu.linkonce.this_module") = {
	.name = KBUILD_MODNAME,
	.init = init_module,
#ifdef CONFIG_MODULE_UNLOAD
	.exit = cleanup_module,
#endif
	.arch = MODULE_ARCH_INIT,
};



static const struct modversion_info ____versions[]
__used __section("__versions") = {
	{ 0xe914e41e, "strcpy" },
	{ 0xaabb1e65, "usb_alloc_urb" },
	{ 0xddf6ad7a, "completion_done" },
	{ 0x70b0605f, "usb_anchor_urb" },
	{ 0x9dcb80d8, "usb_free_urb" },
	{ 0x7b6b1c20, "devlink_unregister" },
	{ 0xa4696429, "can_free_echo_skb" },
	{ 0x4a3ad70e, "wait_for_completion_timeout" },
	{ 0x36a78de3, "devm_kmalloc" },
	{ 0xd98aced1, "can_put_echo_skb" },
	{ 0x8dfc0fe6, "usb_alloc_coherent" },
	{ 0xc13ddddd, "consume_skb" },
	{ 0xd3207e27, "can_get_echo_skb" },
	{ 0x656e4a6e, "snprintf" },
	{ 0xa6257a2f, "complete" },
	{ 0x607c4683, "devlink_info_version_fixed_put" },
	{ 0xa7c65021, "alloc_canfd_skb" },
	{ 0x608741b5, "__init_swait_queue_head" },
	{ 0xa728742c, "usb_register_driver" },
	{ 0x1116d20e, "devlink_port_attrs_set" },
	{ 0x4829a47e, "memcpy" },
	{ 0x37a0cba, "kfree" },
	{ 0xc1a5f581, "devlink_alloc_ns" },
	{ 0x7184f851, "devlink_register" },
	{ 0xe4e358c8, "devlink_free" },
	{ 0x7bd7849f, "netdev_warn" },
	{ 0x34db050b, "_raw_spin_lock_irqsave" },
	{ 0x8256ca07, "open_candev" },
	{ 0x3c3784a1, "netdev_err" },
	{ 0xb1647fc2, "devlink_info_version_running_put" },
	{ 0xf5edea2e, "___ratelimit" },
	{ 0xb8252ecf, "priv_to_devlink" },
	{ 0x6fbe60ba, "usb_bulk_msg" },
	{ 0xf0fdf6cb, "__stack_chk_fail" },
	{ 0xb2fcb56d, "queue_delayed_work_on" },
	{ 0xe23a54a3, "alloc_can_skb" },
	{ 0x962c8ae1, "usb_kill_anchored_urbs" },
	{ 0xb2f34cce, "netif_device_detach" },
	{ 0x7f3723b1, "unregister_candev" },
	{ 0x676d5740, "can_ethtool_op_get_ts_info_hwts" },
	{ 0x4ca11597, "usb_submit_urb" },
	{ 0x3bb3b979, "_dev_info" },
	{ 0x45b13818, "can_change_state" },
	{ 0x7e801e71, "can_change_mtu" },
	{ 0x7e595fc, "can_dropped_invalid_skb" },
	{ 0xa073ddda, "devlink_port_unregister" },
	{ 0xbbd8f39f, "_dev_err" },
	{ 0x3e9f8208, "init_net" },
	{ 0xbd9f15bf, "usb_free_coherent" },
	{ 0xa94d58e3, "free_candev" },
	{ 0xb55b6867, "sk_skb_reason_drop" },
	{ 0x32c8bf9c, "alloc_candev_mqs" },
	{ 0x6047ede6, "can_fd_len2dlc" },
	{ 0xf7a93e0e, "netdev_printk" },
	{ 0xf12d9387, "can_fd_dlc2len" },
	{ 0x294c1286, "can_eth_ioctl_hwts" },
	{ 0x1e5b8225, "usb_deregister" },
	{ 0xd35cce70, "_raw_spin_unlock_irqrestore" },
	{ 0xdae32b06, "netif_tx_wake_queue" },
	{ 0x3dad9978, "cancel_delayed_work" },
	{ 0x1c907576, "close_candev" },
	{ 0xdcb764ad, "memset" },
	{ 0xc5d5e114, "_dev_warn" },
	{ 0x2c66ac85, "devlink_info_serial_number_put" },
	{ 0xd9a5ea54, "__init_waitqueue_head" },
	{ 0x6d729df8, "netif_rx" },
	{ 0x5a19a11d, "can_bus_off" },
	{ 0x29c998f4, "usb_unanchor_urb" },
	{ 0x15ba50a6, "jiffies" },
	{ 0x9fa7184a, "cancel_delayed_work_sync" },
	{ 0xc6f46339, "init_timer_key" },
	{ 0x5443de3e, "__kmalloc_cache_noprof" },
	{ 0x3daea590, "netif_carrier_off" },
	{ 0xffeedf6a, "delayed_work_timer_fn" },
	{ 0x817f23b0, "devlink_priv" },
	{ 0x1f8d4242, "devlink_port_register_with_ops" },
	{ 0xf73c8d96, "netif_carrier_on" },
	{ 0xa65c6def, "alt_cb_patch_nops" },
	{ 0xd54a3432, "alloc_can_err_skb" },
	{ 0xaac2803c, "register_candev" },
	{ 0x4fc61f86, "kmalloc_caches" },
	{ 0xb7dd1970, "netdev_info" },
	{ 0x2d3385d3, "system_wq" },
	{ 0x474e54d2, "module_layout" },
};

MODULE_INFO(depends, "can-dev");

MODULE_ALIAS("usb:v0BFDp000Ad*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp000Bd*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp000Cd*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp000Ed*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp000Fd*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0010d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0011d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0012d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0013d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0016d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0017d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0018d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0019d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp001Ad*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp001Bd*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp001Cd*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp001Dd*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0022d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0023d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0027d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0120d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0121d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0122d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0123d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0124d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0126d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0127d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0128d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0004d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0002d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0005d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0003d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0102d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0104d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0105d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0106d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0107d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0108d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0109d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp010Ad*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp010Bd*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp010Cd*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp010Dd*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp010Ed*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0111d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0112d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0113d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0114d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0115d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0116d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0117d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0118d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp0119d*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp011Ad*dc*dsc*dp*ic*isc*ip*in*");
MODULE_ALIAS("usb:v0BFDp011Bd*dc*dsc*dp*ic*isc*ip*in*");

MODULE_INFO(srcversion, "3738E1644042E754CF6E5CE");

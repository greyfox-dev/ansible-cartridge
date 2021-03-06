# Hack ansible.module_utils.helpers import
import sys
import module_utils.helpers as helpers
sys.modules['ansible.module_utils.helpers'] = helpers

import os
sys.path.append(os.path.dirname(__file__))

import unittest
from parameterized import parameterized
from instance import Instance

from helpers import set_box_cfg

import itertools

from library.cartridge_needs_restart import needs_restart


def call_needs_restart(control_sock,
                       restarted=None,
                       appname=Instance.APPNAME,
                       instance_conf_file=Instance.INSTANCE_CONF_PATH,
                       conf_section_name=Instance.CONF_SECTION,
                       config={},
                       cluster_cookie=Instance.COOKIE,
                       cartridge_defaults={},
                       stateboard=False):
    return needs_restart({
        'restarted': restarted,
        'control_sock': control_sock,
        'appname': appname,
        'instance_conf_file': instance_conf_file,
        'conf_section_name': conf_section_name,
        'cluster_cookie': cluster_cookie,
        'cartridge_defaults': cartridge_defaults,
        'config': config,
        'stateboard': stateboard,
    })


class TestNeedsRestart(unittest.TestCase):
    def setUp(self):
        self.cookie = 'secret'
        self.console_sock = './tmp/x.sock'

        self.instance = Instance(self.console_sock, self.cookie)
        self.instance.start()

    def test_restart_forced(self):
        res = call_needs_restart(
            control_sock=self.console_sock,
            restarted=True
        )
        self.assertTrue(res.success, msg=res.msg)
        self.assertTrue(res.changed)

    def test_restart_disabled(self):
        res = call_needs_restart(
            control_sock=self.console_sock,
            restarted=False
        )
        self.assertTrue(res.success, msg=res.msg)
        self.assertFalse(res.changed)

    def test_instance_not_started(self):
        # console sock doesn't exists
        self.instance.remove_file(self.console_sock)

        res = call_needs_restart(
            control_sock=self.console_sock
        )

        self.assertTrue(res.success, msg=res.msg)
        self.assertTrue(res.changed)

        # cannot connect to console sock
        bad_socket_path = 'bad-socket-path'
        self.instance.write_file(bad_socket_path)

        res = call_needs_restart(
            control_sock=bad_socket_path
        )

        self.assertTrue(res.success, msg=res.msg)
        self.assertTrue(res.changed)

    def test_box_cfg_is_function(self):
        param_name = 'some-param'
        old_value = 'old-value'
        new_value = 'new-value'

        self.instance.set_box_cfg_function()

        self.instance.set_instance_config({
            param_name: old_value,
        })

        # nothing changed
        res = call_needs_restart(
            control_sock=self.console_sock,
            config={
                param_name: old_value,
            },
        )

        self.assertTrue(res.success, msg=res.msg)
        self.assertTrue(res.changed)

        # param was changed
        res = call_needs_restart(
            control_sock=self.console_sock,
            config={
                param_name: new_value,
            },
        )

        self.assertTrue(res.success, msg=res.msg)
        self.assertTrue(res.changed)

    def test_code_was_updated(self):
        # code was updated today, socket yesterday - needs restart
        self.instance.set_path_mtime(self.instance.APP_CODE_PATH, self.instance.DATE_TODAY)
        self.instance.set_path_mtime(self.console_sock, self.instance.DATE_YESTERDAY)

        res = call_needs_restart(control_sock=self.console_sock)

        self.assertTrue(res.success, msg=res.msg)
        self.assertTrue(res.changed)

    @parameterized.expand(
        itertools.product(
            ["instance", "stateboard"],
            ["memtx_memory", "vinyl_memory"],
        )
    )
    def test_config_changed(self, instance_type, memory_param_name):
        param_name = 'param'
        param_current_value = 'current-value'
        param_new_value = 'new-value'

        current_memory_size = 100
        memtx_memory_new_value = 200

        stateboard = instance_type == 'stateboard'

        self.instance.set_instance_config({
            param_name: param_current_value,
            memory_param_name: current_memory_size
        })
        set_box_cfg(self.instance, **{memory_param_name: current_memory_size})

        # nothing changed
        res = call_needs_restart(
            control_sock=self.console_sock,
            config={
                param_name: param_current_value,
                memory_param_name: current_memory_size
            },
            stateboard=stateboard,
        )
        self.assertTrue(res.success, msg=res.msg)
        self.assertFalse(res.changed)

        # param changed, memory size not
        res = call_needs_restart(
            control_sock=self.console_sock,
            config={
                param_name: param_new_value,
                memory_param_name: current_memory_size
            },
            stateboard=stateboard
        )
        self.assertTrue(res.success, msg=res.msg)
        self.assertTrue(res.changed)

        # param isn't changed
        # memory size is changed in config
        # but isn't changed on instance
        set_box_cfg(self.instance, **{memory_param_name: current_memory_size})
        res = call_needs_restart(
            control_sock=self.console_sock,
            config={
                param_name: param_current_value,
                memory_param_name: memtx_memory_new_value
            },
            stateboard=stateboard
        )
        self.assertTrue(res.success, msg=res.msg)
        self.assertTrue(res.changed)

        # param isn't changed
        # memory size is changed in config
        # and changed on instance
        set_box_cfg(self.instance, **{memory_param_name: memtx_memory_new_value})
        res = call_needs_restart(
            control_sock=self.console_sock,
            config={
                param_name: param_current_value,
                memory_param_name: memtx_memory_new_value
            },
            stateboard=stateboard
        )
        self.assertTrue(res.success, msg=res.msg)
        self.assertFalse(res.changed)

        # param is changed
        # memory size is changed in config
        # and changed on instance
        set_box_cfg(self.instance, **{memory_param_name: memtx_memory_new_value})
        res = call_needs_restart(
            control_sock=self.console_sock,
            config={
                param_name: param_new_value,
                memory_param_name: memtx_memory_new_value
            },
            stateboard=stateboard
        )
        self.assertTrue(res.success, msg=res.msg)
        self.assertTrue(res.changed)

    @parameterized.expand(
        itertools.product(
            ["instance", "stateboard"],
            ["memtx_memory", "vinyl_memory"],
        )
    )
    def test_app_config_changed(self, instance_type, memory_param_name):
        param_name = 'param'
        param_current_value = 'current-value'
        param_new_value = 'new-value'

        current_memory_size = 100
        memtx_memory_new_value = 200

        stateboard = instance_type == 'stateboard'

        self.instance.set_app_config({
            param_name: param_current_value,
            memory_param_name: current_memory_size
        })
        set_box_cfg(self.instance, **{memory_param_name: current_memory_size})

        # nothing changed
        res = call_needs_restart(
            control_sock=self.console_sock,
            cartridge_defaults={
                param_name: param_current_value,
                memory_param_name: current_memory_size
            },
            stateboard=stateboard
        )
        self.assertTrue(res.success, msg=res.msg)
        self.assertFalse(res.changed)

        # param changed, memory size not
        res = call_needs_restart(
            control_sock=self.console_sock,
            cartridge_defaults={
                param_name: param_new_value,
                memory_param_name: current_memory_size
            },
            stateboard=stateboard
        )
        self.assertTrue(res.success, msg=res.msg)
        if not stateboard:
            self.assertTrue(res.changed)
        else:
            self.assertFalse(res.changed)

        # param isn't changed
        # memory size is changed in config
        # but isn't changed on instance
        set_box_cfg(self.instance, **{memory_param_name: current_memory_size})
        res = call_needs_restart(
            control_sock=self.console_sock,
            cartridge_defaults={
                param_name: param_current_value,
                memory_param_name: memtx_memory_new_value
            },
            stateboard=stateboard
        )
        self.assertTrue(res.success, msg=res.msg)
        if not stateboard:
            self.assertTrue(res.changed)
        else:
            self.assertFalse(res.changed)

        # param isn't changed
        # memory size is changed in config
        # and changed on instance
        set_box_cfg(self.instance, **{memory_param_name: memtx_memory_new_value})
        res = call_needs_restart(
            control_sock=self.console_sock,
            cartridge_defaults={
                param_name: param_current_value,
                memory_param_name: memtx_memory_new_value
            },
            stateboard=stateboard
        )
        self.assertTrue(res.success, msg=res.msg)
        self.assertFalse(res.changed)

        # param is changed
        # memory size is changed in config
        # and changed on instance
        set_box_cfg(self.instance, **{memory_param_name: memtx_memory_new_value})
        res = call_needs_restart(
            control_sock=self.console_sock,
            cartridge_defaults={
                param_name: param_new_value,
                memory_param_name: memtx_memory_new_value
            },
            stateboard=stateboard
        )
        self.assertTrue(res.success, msg=res.msg)
        if not stateboard:
            self.assertTrue(res.changed)
        else:
            self.assertFalse(res.changed)

    @parameterized.expand([
        ["memtx_memory"],
        ["vinyl_memory"],
    ])
    def test_memory_size_changed(self, memory_param_name):
        current_memory_size = 100
        new_memory_size_instance = 200
        new_memory_size_app = 300

        self.instance.set_app_config({
            memory_param_name: current_memory_size
        })
        self.instance.set_instance_config({
            memory_param_name: current_memory_size
        })
        set_box_cfg(self.instance, **{memory_param_name: current_memory_size})

        # nothing changed
        res = call_needs_restart(
            control_sock=self.console_sock,
            config={
                memory_param_name: current_memory_size
            },
            cartridge_defaults={
                memory_param_name: current_memory_size
            }
        )
        self.assertTrue(res.success, msg=res.msg)
        self.assertFalse(res.changed)

        # memory size changed only in cartridge_defaults
        res = call_needs_restart(
            control_sock=self.console_sock,
            config={
                memory_param_name: current_memory_size
            },
            cartridge_defaults={
                memory_param_name: new_memory_size_instance
            }
        )
        self.assertTrue(res.success, msg=res.msg)
        self.assertFalse(res.changed)

        # memory size changed both in cartridge_defaults and config
        res = call_needs_restart(
            control_sock=self.console_sock,
            config={
                memory_param_name: new_memory_size_instance
            },
            cartridge_defaults={
                memory_param_name: new_memory_size_app
            }
        )
        self.assertTrue(res.success, msg=res.msg)
        self.assertTrue(res.changed)

        # memory size changed both in cartridge_defaults and config
        # memory size on instance is equal to value from cartridge_defaults
        set_box_cfg(self.instance, **{memory_param_name: new_memory_size_app})
        res = call_needs_restart(
            control_sock=self.console_sock,
            config={
                memory_param_name: new_memory_size_instance
            },
            cartridge_defaults={
                memory_param_name: new_memory_size_app
            }
        )
        self.assertTrue(res.success, msg=res.msg)
        self.assertTrue(res.changed)

        # memory size changed both in cartridge_defaults and config
        # memory size on instance is equal to value from config
        set_box_cfg(self.instance, **{memory_param_name: new_memory_size_instance})
        res = call_needs_restart(
            control_sock=self.console_sock,
            config={
                memory_param_name: new_memory_size_instance
            },
            cartridge_defaults={
                memory_param_name: new_memory_size_app
            }
        )
        self.assertTrue(res.success, msg=res.msg)
        self.assertFalse(res.changed)

    def tearDown(self):
        self.instance.stop()

from typing import List
from unittest import TestCase

from PyCrypCli.client import Client
from PyCrypCli.exceptions import AlreadyOwnADeviceException, DeviceNotFoundException
from PyCrypCli.game_objects import Device

from database import execute
from tests.test_server import setup_account, super_password, super_uuid
from util import get_client, is_uuid, uuid


def clear_devices():
    execute("TRUNCATE device_device")


def setup_device(n=1) -> List[str]:
    clear_devices()
    out = []
    for i in range(n):
        out.append(uuid())
        execute(
            "INSERT INTO device_device (uuid, name, owner, powered_on) VALUES (%s, %s, %s, %s)",
            out[-1],
            f"test{i + 1}",
            super_uuid,
            i % 2 == 0,
        )
    return out


class TestDevice(TestCase):
    @classmethod
    def setUpClass(cls):
        setup_account()
        cls.client: Client = get_client()
        cls.client.login("super", super_password)

    @classmethod
    def tearDownClass(cls: "TestDevice"):
        cls.client.close()

    def test_starter_device_failed(self):
        setup_device()

        with self.assertRaises(AlreadyOwnADeviceException):
            self.client.ms("device", ["device", "starter_device"])

    def test_starter_device_successful(self):
        clear_devices()

        result = self.client.ms("device", ["device", "starter_device"])
        self.assertIsInstance(result, dict)
        self.assertEqual(["name", "owner", "powered_on", "uuid"], sorted(result))
        self.assertRegex(result["name"], r"^[a-zA-Z0-9\-_]{1,15}$")
        self.assertEqual(super_uuid, result["owner"])
        self.assertEqual(True, result["powered_on"])
        self.assertTrue(is_uuid(result["uuid"]))

    def test_ping_not_found(self):
        clear_devices()

        with self.assertRaises(DeviceNotFoundException):
            self.client.ms("device", ["device", "ping"], device_uuid=uuid())

    def test_ping_successful(self):
        (device_uuid,) = setup_device()

        self.assertEqual({"online": True}, self.client.ms("device", ["device", "ping"], device_uuid=device_uuid))
        execute("UPDATE device_device SET powered_on=false WHERE uuid=%s", device_uuid)
        self.assertEqual({"online": False}, self.client.ms("device", ["device", "ping"], device_uuid=device_uuid))

    def test_info_not_found(self):
        clear_devices()

        with self.assertRaises(DeviceNotFoundException):
            self.client.ms("device", ["device", "info"], device_uuid=uuid())

    def test_info_successful(self):
        clear_devices()
        device = Device.starter_device(self.client)

        result = self.client.ms("device", ["device", "info"], device_uuid=device.uuid)

        self.assertIsInstance(result, dict)
        self.assertEqual(["hardware", "name", "owner", "powered_on", "uuid"], sorted(result))
        self.assertEqual(device.uuid, result["uuid"])
        self.assertEqual(True, result["powered_on"])
        self.assertEqual(super_uuid, result["owner"])
        self.assertEqual(device.name, result["name"])

        hardware: List[dict] = result["hardware"]
        self.assertIsInstance(hardware, list)
        self.assertEqual(7, len(hardware))
        types = {"mainboard", "cpu", "processorCooler", "ram", "disk", "powerPack", "case"}
        for element in hardware:
            self.assertIsInstance(element, dict)
            self.assertEqual(["device_uuid", "hardware_element", "hardware_type", "uuid"], sorted(element))
            self.assertEqual(device.uuid, element["device_uuid"])
            self.assertTrue(is_uuid(element["uuid"]))
            self.assertIn(element["hardware_type"], types)
            types.remove(element["hardware_type"])
            self.assertRegex(element["hardware_element"], r"^[a-zA-Z0-9 .-]+$")

    def test_all(self):
        devices = {x: i for i, x in enumerate(setup_device(3))}

        result = self.client.ms("device", ["device", "all"])
        self.assertIsInstance(result, dict)
        self.assertEqual(["devices"], list(result))
        self.assertIsInstance(result["devices"], list)
        self.assertEqual(3, len(result["devices"]))
        for device in result["devices"]:
            self.assertIsInstance(device, dict)
            self.assertEqual(["name", "owner", "powered_on", "uuid"], sorted(device))
            device_uuid = device["uuid"]
            self.assertTrue(is_uuid(device_uuid))
            self.assertIn(device_uuid, devices)
            pos = devices[device_uuid]
            self.assertEqual(f"test{pos + 1}", device["name"])
            devices.pop(device_uuid)
            self.assertEqual(super_uuid, device["owner"])
            self.assertEqual(pos % 2 == 0, device["powered_on"])

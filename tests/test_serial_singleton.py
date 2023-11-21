import unittest

from serial_singleton import SerialSingleton, SerialSingletonException


class Child1(SerialSingleton):
    pass


class Child2(SerialSingleton):
    pass


class TestSingleton(unittest.TestCase):
    def test_unconnected(self):
        ser = Child1(connect=False)
        assert ser.is_open is False

    def test_singleton(self):
        # create a few instances of Child1
        ser1 = Child1(connect=False)
        ser2 = Child1(connect=False)
        ser3 = Child1('FakePort3', connect=False)
        ser4 = Child1('FakePort4', connect=False)
        ser5 = Child1(port='FakePort4', connect=False)

        # assert that a port blocked by *another* SerialSingleton child can't be used
        with self.assertRaises(SerialSingletonException):
            Child2('FakePort4')

        # assert that port cannot be changed after initialization
        with self.assertRaises(SerialSingletonException):
            ser5.port = 'some_other_port'

        # assert singleton behavior
        assert ser1 is ser2
        assert ser1 is not ser3
        assert ser3 is not ser4
        assert ser4 is ser5

    def test_set_port(self):
        ser = Child1(connect=False)
        self.assertRaises(Exception, ser.setPort)

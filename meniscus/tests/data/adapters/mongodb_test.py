import unittest

from meniscus.config import init_config, get_config

from meniscus.data import adapters
from meniscus.data.handler import datasource_handler


def suite():
    suite = unittest.TestSuite()
    suite.addTest(WhenConnectingToLiveMongoDB())

    return suite


class WhenConnectingToLiveMongoDB(unittest.TestCase):

    def setUp(self):
        init_config(['--config-file', 'meniscus.cfg.example'])

    def test_mongodb_adapter(self):
        conf = get_config()
        handler = datasource_handler(conf)
        handler.connect()

        handler.put('test', {'name': 'test', 'value': 1})
        test_obj = handler.find_one('test', {'name': 'test'})
        self.assertEqual(1, test_obj['value'])
        
        handler.delete('test', {'name': 'test'})
        test_obj = handler.find_one('test', {'name': 'test'})
        self.assertFalse(test_obj)
        
        handler.close()


if __name__ == '__main__':
    unittest.main()

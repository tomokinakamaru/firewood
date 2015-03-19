# coding:utf-8

import inspect
import os
import sys
from importlib import import_module
from mapletree import MapleTree, rsp
from mapletree.driver import Driver
from mapletree.routetree import ExceptionTree, RequestTree
from mapletree.signing import Signing
from . import logger


class Firewood(object):
    def __init__(self):
        self.mapletree = MapleTree()

        self.config_package = 'config'
        self.config_stage_f = lambda: os.environ.get('STAGE', 'development')

        self.req_reusables = {'': set(['firewood.default.req'])}
        self.exc_reusables = set(['firewood.default.exc'])

        self.autoloads = set(['firewood.default.session', 'routes'])

        self.session_key = None
        self._signing = None

    @property
    def signing(self):
        if self._signing is None:
            if self.session_key is not None:
                self._signing = Signing(self.session_key)

            else:
                raise Exception('fw.session_key must be configured')

        return self._signing

    @property
    def rsp(self):
        return rsp()

    def __call__(self, environ, start_response):
        try:
            return self.mapletree(environ, start_response)

        except:
            logger.tb()
            start_response('500 Internal Server Error', [])
            return ''

    def run(self, background=False):
        target = os.path.dirname(os.path.abspath(sys.argv[0]))
        driver = Driver(self, 5000, target, 1)
        driver.verbose = False
        if background:
            driver.run_background()

        else:
            driver.run()

    def build(self):
        caller_name = inspect.getmodule(inspect.stack()[1][0]).__name__
        if caller_name == '__main__' and not Driver.is_stub_proc():
            return

        logger.i('Start building app')
        self._build_config()
        self._build_reusables()
        self._build_autoloads()
        self._build_head_methods()
        self._build_options_methods()

    def _build_config(self):
        try:
            self.mapletree.config.load_package(self.config_package)
            self.mapletree.config.stage = self.config_stage_f()

        except ImportError as e:
            fmt = 'Failed to load config package `{}`'
            logger.w(fmt, self.config_pkg)
            logger.tb()

    def _build_reusables(self):
        for prefix, seq in self.req_reusables.items():
            for mname in seq:
                try:
                    m = import_module(mname)
                    for k in dir(m):
                        attr = getattr(m, k)
                        if isinstance(attr, RequestTree):
                            self._build_reusables_request(prefix, attr)

                except ImportError:
                    fmt = 'Failed to merge request reusable `{}`'
                    logger.w(fmt, mname)
                    logger.tb()

        for mname in self.exc_reusables:
            try:
                m = import_module(mname)
                for k in dir(m):
                    attr = getattr(m, k)
                    if isinstance(attr, ExceptionTree):
                        self._build_reusables_exception(attr)

            except ImportError:
                fmt = 'Failed to merge exception reusable `{}`'
                logger.w(fmt, mname)
                logger.tb()

    def _build_reusables_request(self, prefix, rtree):
        self.mapletree.req.merge(rtree, prefix)
        for k, v in rtree.items():
            path = prefix + '/' + '/'.join(k)
            msg = 'Merged request endpoint `{}` for `{}`'.format(v, path)
            logger.i(msg)

    def _build_reusables_exception(self, etree):
        self.mapletree.exc.merge(etree)
        for k, v in etree.items():
            path = '/' + '/'.join(k)
            msg = 'Merged exception endpoint `{}` for `{}`'.format(v, path)
            logger.i(msg)

    def _build_autoloads(self):
        for p in self.autoloads:
            try:
                self.mapletree.scan(p)

            except ImportError:
                logger.w('Failed to import package/module `{}`'.format(p))
                logger.tb()

    def _build_head_methods(self):
        for k, v in self.mapletree.req.items():
            if 'get' in v:
                def _(req):
                    return v['get'](req).body('')

                self.mapletree.req.head('/' + '/'.join(k))(_)

    def _build_options_methods(self):
        for k, v in self.mapletree.req.items():
            def _(req):
                return rsp().header('Allow', ','.join(v.keys()).upper())

            self.mapletree.req.options('/' + '/'.join(k))(_)

    def get(self, path):
        return self.mapletree.req.get(path)

    def post(self, path):
        return self.mapletree.req.post(path)

    def put(self, path):
        return self.mapletree.req.put(path)

    def delete(self, path):
        return self.mapletree.req.delete(path)

    def head(self, path):
        return self.mapletree.req.head(path)

    def options(self, path):
        return self.mapletree.req.options(path)

    def patch(self, path):
        return self.mapletree.req.patch(path)

    def exc(self, exc_cls):
        return self.mapletree.exc(exc_cls)
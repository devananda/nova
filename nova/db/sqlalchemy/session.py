# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Session Handling for SQLAlchemy backend."""

import time

from sqlalchemy.exc import DisconnectionError
from sqlalchemy.exc import OperationalError
import sqlalchemy.interfaces
import sqlalchemy.orm
from sqlalchemy.pool import NullPool
from sqlalchemy.pool import StaticPool

import nova.exception
from nova.exception import DBError
from nova.exception import InvalidUnicodeParameter
import nova.flags as flags
import nova.openstack.common.log as logging


FLAGS = flags.FLAGS
LOG = logging.getLogger(__name__)

_ENGINE = None
_MAKER = None


def get_session(autocommit=True, expire_on_commit=False):
    """Return a SQLAlchemy session."""
    global _MAKER

    if _MAKER is None:
        engine = get_engine()
        _MAKER = get_maker(engine, autocommit, expire_on_commit)

    session = _MAKER()
    session.begin = wrap_db_error(session.begin)
    session.execute = wrap_db_error(session.execute)
    session.flush = wrap_db_error(session.flush)
    session.query = wrap_db_error(session.query)
    return session


def synchronous_switch_listener(dbapi_conn, connection_rec):
    """Switch sqlite connections to non-synchronous mode"""
    dbapi_conn.execute("PRAGMA synchronous = OFF")


def is_db_connection_error(args):
    """Return True if error in connecting to db."""
    # NOTE(adam_g): This is currently MySQL specific and needs to be extended
    #               to support Postgres and others.
    conn_err_codes = ('2002', '2003', '2006')
    for err_code in conn_err_codes:
        if args.find(err_code) != -1:
            return True
    return False


def wrap_db_error(f):
    """Function wrapper to capture DB errors

    If an exception is thrown by the wrapped function,
    determine if it represents a database connection error.
    If so, retry the wrapped function, and repeat until it succeeds
    or we reach a configurable maximum number of retries.
    If it is not a connection error, or we exceeded the retry limit,
    raise a DBError.

    """
    def _wrap_db_error(*args, **kwargs):
        next_interval = FLAGS.sql_retry_interval
        remaining = FLAGS.sql_max_retries
        if remaining == -1:
            remaining = 'infinite'
        while True:
            try:
                return f(*args, **kwargs)
            except UnicodeEncodeError:
                raise InvalidUnicodeParameter()
            except OperationalError, e:
                if is_db_connection_error(e.args[0]):
                    if remaining == 0:
                        LOG.exception(_('DB exceeded retry limit.'))
                        raise DBError(e)
                    if remaining != 'infinite':
                        remaining -= 1
                    LOG.exception(_('DB connection error, '
                                    'retrying in %i seconds.') % next_interval)
                    time.sleep(next_interval)
                    if (FLAGS.sql_inc_retry_interval and
                            next_interval < FLAGS.sql_max_retry_interval):
                        next_interval += 1
                else:
                    LOG.exception(_('DB exception wrapped.'))
                    raise DBError(e)
            except Exception, e:
                LOG.exception(_('DB exception wrapped.'))
                raise DBError(e)

    _wrap_db_error.func_name = f.func_name
    return _wrap_db_error


def get_engine():
    """Return a SQLAlchemy engine."""
    global _ENGINE
    if _ENGINE is None:
        connection_dict = sqlalchemy.engine.url.make_url(FLAGS.sql_connection)

        engine_args = {
            "pool_recycle": FLAGS.sql_idle_timeout,
            "echo": False,
            'convert_unicode': True,
            'pool_reset_on_return': False,
        }

        # Map our SQL debug level to SQLAlchemy's options
        if FLAGS.sql_connection_debug >= 100:
            engine_args['echo'] = 'debug'
        elif FLAGS.sql_connection_debug >= 50:
            engine_args['echo'] = True

        if "sqlite" in connection_dict.drivername:
            engine_args["poolclass"] = NullPool

            if FLAGS.sql_connection == "sqlite://":
                engine_args["poolclass"] = StaticPool
                engine_args["connect_args"] = {'check_same_thread': False}

        _ENGINE = sqlalchemy.create_engine(FLAGS.sql_connection, **engine_args)

        if "sqlite" in connection_dict.drivername:
            if not FLAGS.sqlite_synchronous:
                sqlalchemy.event.listen(_ENGINE, 'connect',
                                        synchronous_switch_listener)

        if (FLAGS.sql_connection_trace and
                _ENGINE.dialect.dbapi.__name__ == 'MySQLdb'):
            import MySQLdb.cursors
            _do_query = debug_mysql_do_query()
            setattr(MySQLdb.cursors.BaseCursor, '_do_query', _do_query)

        try:
            _ENGINE.connect()
        except OperationalError, e:
            if not is_db_connection_error(e.args[0]):
                raise

            next_interval = FLAGS.sql_retry_interval
            remaining = FLAGS.sql_max_retries
            if remaining == -1:
                remaining = 'infinite'
            while True:
                msg = _('SQL connection failed. %s attempts left.')
                LOG.warn(msg % remaining)
                if remaining != 'infinite':
                    remaining -= 1
                time.sleep(next_interval)
                try:
                    _ENGINE.connect()
                    break
                except OperationalError, e:
                    if (remaining != 'infinite' and remaining == 0) or \
                       not is_db_connection_error(e.args[0]):
                        raise
                    if (FLAGS.sql_inc_retry_interval and
                            next_interval < FLAGS.sql_max_retry_interval):
                        next_interval += 1

    return _ENGINE


def get_maker(engine, autocommit=True, expire_on_commit=False):
    """Return a SQLAlchemy sessionmaker using the given engine."""
    query = sqlalchemy.orm.query.Query
    query.all = wrap_db_error(query.all)
    query.first = wrap_db_error(query.first)
    return sqlalchemy.orm.sessionmaker(bind=engine,
                                       autocommit=autocommit,
                                       expire_on_commit=expire_on_commit,
                                       query_cls=query)


def debug_mysql_do_query():
    """Return a debug version of MySQLdb.cursors._do_query"""
    import MySQLdb.cursors
    import traceback

    old_mysql_do_query = MySQLdb.cursors.BaseCursor._do_query

    def _do_query(self, q):
        stack = ''
        for file, line, method, function in traceback.extract_stack():
            # exclude various common things from trace
            if file.endswith('session.py') and method == '_do_query':
                continue
            if file.endswith('api.py') and method == 'wrapper':
                continue
            if file.endswith('utils.py') and method == '_inner':
                continue
            if file.endswith('session.py') and method == '_wrap_db_error':
                continue
            # nova/db/api is just a wrapper around nova/db/sqlalchemy/api
            if file.endswith('nova/db/api.py'):
                continue
            # only trace inside nova
            index = file.rfind('nova')
            if index == -1:
                continue
            stack += "File:%s:%s Method:%s() Line:%s | " \
                    % (file[index:], line, method, function)

        # strip trailing " | " from stack
        if stack:
            stack = stack[:-3]
            qq = "%s /* %s */" % (q, stack)
        else:
            qq = q
        old_mysql_do_query(self, qq)

    # return the new _do_query method
    return _do_query

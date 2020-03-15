'''
SQLAlchemy refers to SQL variants as dialects. An SQLAlchemy Dialect object 
contains information about specific behaviors of the backend, keywords etc.
It also references to the default underlying DB-API implementation (aka Driver) in use. 

Created -       27/08/2017
Last modified - 04/03/2020

Usage:
- Pop a Python shell from sqream_dialect.py's folder, or add it to Python's import path

# Usage snippet - type in in shell or editor
# ------------------------------------------

import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.dialects import registry 

# In-process registering, installing the package not required
registry.register("sqream.sqream_dialect", "sqream_dialect", "SqreamDialect")                                                   

engine = create_engine("sqream+sqream_dialect://sqream:sqream@localhost:5000/master") 

# As bestowed upon me by Yuval
res = engine.execute('select 1')

for row in res:
    print row

'''

from importlib import import_module    # for importing and returning the module
from sqlalchemy.engine.default import DefaultDialect, DefaultExecutionContext
from sqlalchemy.types import Boolean, LargeBinary, SmallInteger, Integer, BigInteger, Float, Date, DateTime, String, Unicode, UnicodeText
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.dialects import registry 
from sqlalchemy.sql import compiler, crud

try:
    from alembic.ddl.impl import DefaultImpl
except:
    pass
else:
    class SQreamImpl(DefaultImpl):
        ''' Allows Alembic tool to recognize the dialect if installed '''

        __dialect__ = 'sqream'


registry.register("pysqream", "dialect", "SqreamDialect")


sqream_to_alchemy_types = {
    'bool':     Boolean,
    'boolean':  Boolean,
    'ubyte':    TINYINT,
    'smallint': SmallInteger,
    'int':      Integer,
    'integer':  Integer,
    'bigint':   BigInteger,
    'float':    Float,
    'double':   Float,
    'real':     Float,
    'date':     Date,
    'datetime': DateTime,  
    'timestamp':DateTime,
    'varchar':  String,
    'nvarchar': Unicode   
} 


def printdbg(message, dbg = False):

    if dbg:
        print (message)


class SqreamExecutionContext(DefaultExecutionContext):

    '''
    def __init__(self, dialect, connection, dbapi_connection, compiled_ddl):
        super(SqreamExecutionContext, self).__init__(dialect, connection, dbapi_connection, compiled_ddl)
    '''

    executemany = True

    def __init__(self, **kwargs):
        super(SqreamExecutionContext, self).__init__(**kwargs)

        self.cursor = self.create_cursor() # root_connection

    def _setup_crud_result_proxy(self):
        if self.isinsert and not self.executemany:
            if (
                not self._is_implicit_returning
                and not self.compiled.inline
                and self.dialect.postfetch_lastrowid
            ):

                self._setup_ins_pk_from_lastrowid()

            elif not self._is_implicit_returning:
                self._setup_ins_pk_from_empty()

        result = self.get_result_proxy()
        if self.isinsert:
            if self._is_implicit_returning:
                row = result.fetchone()
                self.returned_defaults = row
                self._setup_ins_pk_from_implicit_returning(row)
                result._soft_close()
                result._metadata = None
            elif not self._is_explicit_returning:
                result._soft_close()
                result._metadata = None
        elif self.isupdate and self._is_implicit_returning:
            row = result.fetchone()
            self.returned_defaults = row
            result._soft_close()
            result._metadata = None
        elif result._metadata is None:
            # no results, get rowcount
            # (which requires open cursor on some drivers
            # such as kintersbasdb, mxodbc)
            result.rowcount
            
            if not result._soft_closed:
                result._soft_closed = True
                result.cursor.close()
                # '''
                if result._autoclose_connection:
                    result.connection.close()
                # '''


        return result


'''
ischema_names = {
    'BOOLEAN': Boolean,
    'TINYINT' : TINYINT,
    'DATE': Date,
    'DATETIME': DateTime,

}
'''


class TINYINT(TINYINT):
    ''' Allows describing tables via the ORM mechanism. Complemented in 
        SqreamTypeCompiler '''  
    
    pass


class SqreamTypeCompiler(compiler.GenericTypeCompiler):
    ''' Get the SQream string names for SQLAlchemy types, useful for ORM
        generated Create queries '''

    def visit_BOOLEAN(self, type_, **kw):
    
        return "BOOL"

    def visit_TINYINT(self, type_, **kw):
    
        return "TINYINT"

    '''
    def visit_large_binary(self, type_, **kw):

        if type_.length == 1:
            return "TINYINT"
        
        return self.visit_BLOB(type_)
    # '''
    


class SqreamSQLCompiler(compiler.SQLCompiler):
    ''' Overriding visit_insert behavior of generating SQL with multiple 
       (?,?) clauses for ORM inserts with parameters  '''
    

    def visit_insert(self, insert_stmt, asfrom=False, **kw):
            toplevel = not self.stack

            self.stack.append(
                {
                    "correlate_froms": set(),
                    "asfrom_froms": set(),
                    "selectable": insert_stmt,
                }
            )

            crud_params = crud._setup_crud_params(
                self, insert_stmt, crud.ISINSERT, **kw
            )

            if (
                not crud_params
                and not self.dialect.supports_default_values
                and not self.dialect.supports_empty_insert
            ):
                raise exc.CompileError(
                    "The '%s' dialect with current database "
                    "version settings does not support empty "
                    "inserts." % self.dialect.name
                )

            if insert_stmt._has_multi_parameters:
                if not self.dialect.supports_multivalues_insert:
                    raise exc.CompileError(
                        "The '%s' dialect with current database "
                        "version settings does not support "
                        "in-place multirow inserts." % self.dialect.name
                    )
                crud_params_single = crud_params[0]
            else:
                crud_params_single = crud_params

            preparer = self.preparer
            supports_default_values = self.dialect.supports_default_values

            text = "INSERT "

            if insert_stmt._prefixes:
                text += self._generate_prefixes(
                    insert_stmt, insert_stmt._prefixes, **kw
                )

            text += "INTO "
            table_text = preparer.format_table(insert_stmt.table)

            if insert_stmt._hints:
                _, table_text = self._setup_crud_hints(insert_stmt, table_text)

            text += table_text

            if crud_params_single or not supports_default_values:
                text += " (%s)" % ", ".join(
                    [preparer.format_column(c[0]) for c in crud_params_single]
                )

            if self.returning or insert_stmt._returning:
                returning_clause = self.returning_clause(
                    insert_stmt, self.returning or insert_stmt._returning
                )

                if self.returning_precedes_values:
                    text += " " + returning_clause
            else:
                returning_clause = None

            if insert_stmt.select is not None:
                select_text = self.process(self._insert_from_select, **kw)

                if self.ctes and toplevel and self.dialect.cte_follows_insert:
                    text += " %s%s" % (self._render_cte_clause(), select_text)
                else:
                    text += " %s" % select_text
            elif not crud_params and supports_default_values:
                text += " DEFAULT VALUES"
            
            # <Overriding part> - money is in crud_params[0]
            elif insert_stmt._has_multi_parameters:
                insert_single_values_expr = ", ".join([c[1] for c in crud_params[0]])
                text += " VALUES (%s)" % insert_single_values_expr
                if toplevel:
                    self.insert_single_values_expr = insert_single_values_expr
            # </Overriding part>
            else:
                insert_single_values_expr = ", ".join([c[1] for c in crud_params])
                text += " VALUES (%s)" % insert_single_values_expr
                if toplevel:
                    self.insert_single_values_expr = insert_single_values_expr

            if insert_stmt._post_values_clause is not None:
                post_values_clause = self.process(
                    insert_stmt._post_values_clause, **kw
                )
                if post_values_clause:
                    text += " " + post_values_clause

            if returning_clause and not self.returning_precedes_values:
                text += " " + returning_clause

            if self.ctes and toplevel and not self.dialect.cte_follows_insert:
                text = self._render_cte_clause() + text

            self.stack.pop(-1)

            if asfrom:
                return "(" + text + ")"
            else:
                return text




class SqreamDialect(DefaultDialect):
    ''' dbapi() classmethod, get_table_names() and get_columns() seem to be the 
        important ones for Apache Superset. get_pk_constraint() returning an empty
        sequence also needs to be in place  ''' 
    
    name = 'sqream'
    default_paramstyle = 'qmark'
    supports_native_boolean = True
    supports_multivalues_insert = True
    # preparer = 
    # ddl_compiler = 
    type_compiler = SqreamTypeCompiler
    statement_compiler = SqreamSQLCompiler
    # execution_ctx_cls = SqreamExecutionContext
    # ischema_names = ischema_names
    Tinyint = TINYINT

    def __init__(self, **kwargs):
        super(SqreamDialect, self).__init__(self, **kwargs)


    @classmethod
    def dbapi(cls):
        ''' The minimal reqruirement to get an engine.connect() going'''
        # return dbapi

        # return __import__("sqream_dbapi", fromlist="sqream")

        try:
            from pysqream import dbapi as dbapi
        except:
            import dbapi
            
        return dbapi
        # return import_module('wrapper')


    def initialize(self, connection):
        self.default_schema_name = 'public'


    def get_table_names(self, connection, schema=None, **kw):
        ''' Allows showing table names when connecting database to Apache Superset'''

        query = "select * from sqream_catalog.tables"
        return [table_spec[3] for table_spec in connection.execute(query).fetchall()]

    
    def get_schema_names(self, connection, schema=None, **kw):
        ''' Return schema names '''

        query = "select get_schemas()"
        return [schema for schema, database in connection.execute(query).fetchall()]


    def has_table(self, connection, table_name, schema = None):
        return table_name in self.get_table_names(connection, schema)
    

    def get_columns(self, connection, table_name, schema=None, **kwargs):
        ''' Used by SQLAlchemy's Table() which is called by Superset's get_table()
            when trying to add a new table to the sources'''

        query = "select get_ddl('{}')".format(table_name)
        table_ddl = connection.execute(query).fetchall()[0][0].split('\n')
        schema = table_ddl[0].split()[2].split('.')[0]
        columns_meta = []
        
        # 1st (0) entry is "create table", last 5 are closing parantheses and other jib
        for col in table_ddl[1:-5]:    
            col_meta = col.split()
            col_name = col_meta[0][1:-1]
            col_type = sqream_to_alchemy_types[col_meta[1].split('(')[0]]           
            col_nullable = True if col_meta[2] == 'null' else False
            c = {
                'name': col_name,
                'type': col_type,
                'nullable': col_nullable,
                'default': None
                }
            printdbg (c)
            columns_meta.append(c)       # add default extraction if exists in sqream

        
        return columns_meta

    
    def do_execute(self, cursor, statement, parameters, context=None):
        
        if statement.lower().startswith('insert') and '?' in statement: # and type(parameters[0] not in (tuple, list)):
            cursor.executemany(statement, parameters, data_as='alchemy_flat_list')
        else:
            cursor.execute(statement, parameters)


    def _get_server_version_info(self, connection):
        
        query = 'select get_sqream_server_version()'
        sqream_version = connection.execute(query).fetchall()[0][0]

        return sqream_version


    def get_pk_constraint(self, connection, table_name, schema=None, **kw):
        ''' One of the unimplemented functions in Alc's engines/interfaces.py. 
            Apparently needs an empty implememntation at the least for reflecting
            a table '''
        return {}


    def get_foreign_keys(self, connection, table_name, schema=None, **kw):
        return []

    
    def get_indexes(self, connection, table_name, schema=None, **kw):
        return []

    
    def do_commit(self, connection):
        connection.commit()

    
    def do_rollback(self, connection):
        connection.rollback()

"""通过原生异步绑定访问 D1，使用参数绑定避免拼接用户输入。"""


def to_python(value):
    """将运行时的 JavaScript 结果转换成普通 Python 对象。"""
    if hasattr(value, 'to_py'):
        return value.to_py()
    return value


class Database:
    def __init__(self, binding):
        """保存当前请求对应的数据库绑定。"""
        self.binding = binding

    def statement(self, sql, parameters=()):
        """准备参数化语句，布尔值转换为 SQLite 整数。"""
        statement = self.binding.prepare(sql)
        values = tuple(int(value) if isinstance(value, bool) else value for value in parameters)
        return statement.bind(*values) if values else statement

    async def all(self, sql, parameters=()):
        """返回查询结果列表。"""
        result = await self.statement(sql, parameters).all()
        return to_python(result.results)

    async def first(self, sql, parameters=()):
        """返回首条记录，不存在时返回空值。"""
        return to_python(await self.statement(sql, parameters).first())

    async def run(self, sql, parameters=()):
        """执行单条写入语句并返回元数据。"""
        result = await self.statement(sql, parameters).run()
        return to_python(result.meta)

    async def batch(self, statements):
        """通过 D1 批处理在同一事务中执行相关写入。"""
        from pyodide.ffi import to_js
        return to_python(await self.binding.batch(to_js([self.statement(sql, values) for sql, values in statements])))

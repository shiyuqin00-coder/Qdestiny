def TEST(cls):
    """
    服务装饰器，用于标记要注册的服务类
    """
    cls._is_service = True
    return cls
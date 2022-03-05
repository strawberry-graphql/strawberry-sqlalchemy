from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyLoader

def test_loader_init():
    loader = StrawberrySQLAlchemyLoader(bind=None)
    assert loader.bind is None
    assert loader._loaders == {}

def test_loader_for():
    pass
import pytest

class AsyncReturnWrapper:
    def __init__(self, value):
        self.value = value
    def __call__(self, *args, **kwargs):
        async def inner():
            return self.value
        return inner()

def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as asyncio")

@pytest.fixture(autouse=True)
def add_helpers(request):
    pytest.helpers = type('Helpers', (), {'async_return': AsyncReturnWrapper})()

import importlib
import pkgutil


def include_routers(app, package_name, package_path):
    # pkgutil.iter_modules를 사용하여 패키지 내의 모든 모듈을 찾음
    for _, module_name, _ in pkgutil.iter_modules(package_path):
        module = importlib.import_module(f"app.{package_name}.{module_name}")
        if hasattr(module, "router"):
            app.include_router(module.router)

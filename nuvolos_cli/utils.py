from tabulate import tabulate
from pydantic import BaseModel


def print_model(model: BaseModel, tablefmt="github"):
    print(tabulate(model.dict(), tablefmt=tablefmt, headers="keys"))


def print_models(models: [BaseModel], tablefmt="github"):
    print(tabulate([m.dict() for m in models], tablefmt=tablefmt, headers="keys"))

from tabulate import tabulate
from pydantic import BaseModel


def print_model(model: BaseModel, tablefmt="plain"):
    print(tabulate(model.model_dump(), tablefmt=tablefmt))


def print_models(models: [BaseModel], tablefmt="plain"):
    print(tabulate([m.model_dump() for m in models], tablefmt=tablefmt))

from repos.repo import Repo


def persist_item(value: str):
    repo = Repo()
    return repo.save(value)

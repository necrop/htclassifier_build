import os


class DerivationTester(object):
    neutral_suffixes = set()
    loaded = False

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            self.__dict__[k] = v
        try:
            self.resources_dir
        except AttributeError:
            pass
        else:
            self.dir = os.path.join(self.resources_dir, 'derivation')
            self.load_data()

    def load_data(self):
        if not DerivationTester.loaded:
            in_file = os.path.join(self.dir, 'neutral_suffixes.txt')
            with open(in_file) as fh:
                for line in fh:
                    suffix = '-' + line.strip()
                    if line:
                        DerivationTester.neutral_suffixes.add(suffix)

    def is_neutral_suffix(self, suffix):
        if suffix in DerivationTester.neutral_suffixes:
            return True
        else:
            return False


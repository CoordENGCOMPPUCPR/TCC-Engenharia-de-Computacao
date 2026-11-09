import os
from PIL import Image
from data.base_dataset import BaseDataset, get_params, get_transform
from data.image_folder import make_dataset

class AlignedDataset(BaseDataset):

    def initialize(self, opt):
        self.opt = opt
        self.root = opt.croot
        self.phase = opt.phase

        self.dir = os.path.join(self.root, self.phase)
        self.paths = sorted(make_dataset(self.dir))

    def __getitem__(self, index):
        path = self.paths[index]
        img = Image.open(path).convert('RGB')

        w, h = img.size
        w2 = w // 2

        # separa esquerda (input) e direita (target)
        A = img.crop((0, 0, w2, h))
        B = img.crop((w2, 0, w, h))

        # gera parâmetros de transform (resize, crop etc)
        params = get_params(self.opt, A.size)

        transform_A = get_transform(self.opt, params)
        transform_B = get_transform(self.opt, params)

        A = transform_A(A)
        B = transform_B(B)

        return {
            'label': A,
            'image': B,
            'instance': A,
            'path': path
        }

    def __len__(self):
        return len(self.paths)

    def name(self):
        return 'AlignedDataset'

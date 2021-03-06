import numpy as np
import math
import os
import json
from shutil import copyfile
import random
import matplotlib.pyplot as plt
from collections import OrderedDict
import csv
import socket

import muon.project.panoptes as panoptes
import muon.config

import muon.data


class Image:
    """
    A group of subjects which are uploaded to Panoptes as a single Image
    """

    def __init__(self, id_, group, subjects, metadata, zoo_id=None):
        self.id = id_
        self.group = group
        self.subjects = subjects
        self.metadata = metadata
        self.zoo_id = zoo_id

    def __str__(self):
        return 'id %d group %d subjects %d metadata %s zooid %s' % \
                (self.id, self.group, len(self.subjects),
                 str(self.metadata), self.zoo_id)

    def __repr__(self):
        return str(self)

    def dump(self):
        return {
            'id': self.id,
            'group': self.group,
            'subjects': [int(i) for i in self.subjects],
            'metadata': self.metadata,
            'zooniverse_id': self.zoo_id
        }

    def dump_manifest(self):
        data = OrderedDict([
            ('id', self.id),
            ('#group', self.group),
            ('image', self.fname()),
            ('#subjects', self.subjects)])
        hide = ['cluster']
        for k, v in self.metadata.items():
            if k not in data:
                if k in hide:
                    k = '#' + k
                data[k] = v

        return data


    @classmethod
    def load(cls, dumped):
        """
        Load Image from an entry in structures file
        """
        kwargs = {
            'id_': dumped['id'],
            'group': dumped['group'],
            'subjects': dumped['subjects'],
            'metadata': dumped['metadata'],
            'zoo_id': dumped['zooniverse_id'],
        }

        return cls(**kwargs)

    def fname(self):
        """
        Filename to use for this subject group
        """
        return 'muon_group_%d_id_%d.png' % (self.group, self.id)

    def plot(self, width, subjects, path=None):
        """
        Generate and save a plot of this image
        """
        subjects = subjects.subset(self.subjects)
        fname = self.fname()

        # Skip if image already exists
        if fname in os.listdir(path):
            return

        if path:
            fname = os.path.join(path, fname)

        offset = .5
        dpi = 100
        fig, meta = subjects.plot_subjects(
            w=width, grid=True, grid_args={'offset': offset}, meta=True)

        metadata = {
            'dpi': dpi,
            'offset': offset,
            **meta
        }
        self.metadata.update({'figure': metadata})

        fig.savefig(fname, dpi=dpi)

        plt.close(fig)

    def at_location(self, x, y):
        """
        Return the subject that should be at the given x,y coordinates
        """
        meta = self.metadata['figure']
        print(meta)
        dpi = meta['dpi']
        offset = meta['offset']*dpi
        height = meta['height']*dpi-offset
        width = meta['width']*dpi-offset

        if 'beta_image' in meta:
            # This image was generated before the offset bug was discovered
            # and need to correct the vertical offset to get the right
            # boundary calculations
            width = meta['width']*dpi*0.97
            height = meta['height']*dpi*0.97
            y = y - 0.03*meta['height']*dpi + offset

        y_ = height/meta['rows']
        x_ = width/meta['cols']
        print('x: ', x)
        print('y: ', y)
        print('offset: ', offset)
        print('width: ', width)
        print('height: ', height)

        print('x_: ', x_)
        print('y_: ', y_)

        x = (x-offset)//x_
        y = (y-offset)//y_

        i = int(x+meta['cols']*y)
        print(i)
        return self.subjects[i]


class Images_Parent:
    _image = Image
    _loaded_images = {}

    def __init__(self, group, images, next_id):
        self.images = images
        self.zoo_map = None
        # TODO load existing structure to not duplicate ids
        self.next_id = next_id
        self.group = group

    def __str__(self):
        s = 'group %s images %d metadata %s' % \
            (str(self.group), len(self.images), self.metadata())
        return s

    def __repr__(self):
        return str(self)

    def get_zoo(self, zoo_id):
        if self.zoo_map is None:
            zoo_map = {}
            for i in self.iter():
                if i.zoo_id:
                    zoo_map[i.zoo_id] = i.id
            self.zoo_map = zoo_map
        return self.images[self.zoo_map[zoo_id]]

    def iter(self):
        for image in self.list():
            yield image

    def list(self):
        return list(self.images.values())

    @classmethod
    def load_group(cls, group, fname=None):
        """
        Load Images object from group entry in structures json file
        """
        if fname is None:
            fname = cls._fname()
        if os.path.isfile(fname):
            with open(fname, 'r') as file:
                data = json.load(file)

        next_id = data['next_id']
        data = data['groups'][str(group)]

        images = OrderedDict()
        for item in data['images']:
            image = cls._image.load(item)
            if image.metadata.get('deleted') is True:
                continue
            images[image.id] = image

        images = cls(group, images, next_id)
        images.metadata(data['metadata'])

        cls._loaded_images[group] = images
        return images

    def metadata(self, new=None):
        pass

    @staticmethod
    def _fname():
        fname = '%s_structure.json' % socket.gethostname()
        return muon.data.path(fname)

    def save_group(self, overwrite=False, backup=None):
        """
        Save the configuration of this Images object to the structures
        json file
Split Images class into parent and main class

Also added splinter function and better structure saving"""
        images = self.list()
        group = str(self.group)

        fname = self._fname()
        data = self._load_data()
        if data:
            if backup is None:
                backup = fname+'.bak'
            copyfile(fname, backup)
        else:
            data = {'groups': {}}

        if group in data['groups'] and not overwrite:
            print('file contents: ', data)
            raise Exception('Refusing to overwrite group (%s) in structure '
                            'file' % group)

        data['groups'][group] = {
            'metadata': self.metadata(),
            'images': [i.dump() for i in images]
        }

        # TODO save to different file per upload...? Or have them all in the
        # same file. Probably want them all in the same file.
        # TODO do we need a separate file per workflow?
        self.update_metadata(data)
        self._save_data(data)

    @classmethod
    def _load_data(cls):
        fname = cls._fname()
        if os.path.isfile(fname):
            with open(fname, 'r') as file:
                data = json.load(file)
            return data

    @classmethod
    def _save_data(cls, data):
        fname = cls._fname()
        with open(fname, 'w') as file:
            json.dump(data, file)

    @classmethod
    def load_metadata(cls, data=None):
        """
        Load metadata stored in the header of the structures json file
        """
        if data is None:
            data = cls._load_data()
        if data:
            next_id = data['next_id']
            group = data['next_group']
        else:
            next_id = 0
            group = 0

        return group, next_id

    def update_metadata(self, data=None):
        if data is None:
            save = False
            data = self._load_data()
        else:
            save = True

        group = max(self.group+1, data['next_group'])
        data['next_group'] = group

        next_id = max(self.next_id, data['next_id'])
        data['next_id'] = next_id

        if save:
            self._save_data(data)
        return data

    @classmethod
    def _list_groups(cls):
        data = cls._load_data()
        return list(data['groups'].keys())

class Images(Images_Parent):
    _image = Image

    def __init__(self, group, images, next_id, **kwargs):
        super().__init__(group, images, next_id)

        self.size = kwargs.get('image_size', 40)
        self.image_dim = kwargs.get('width', 10)
        self.description = kwargs.get('description', None)
        self.permutations = kwargs.get('permutations', 3)

        self._loaded_images[group] = self

    @classmethod
    def new(cls, cluster, **kwargs):
        """
        Create new Images group
        """
        group, next_id = cls.load_metadata()
        images = cls(group, None, next_id, **kwargs)
        images.generate_structure(cluster)

        return images

    def metadata(self, new=None):
        if new is None:
            return {
                'size': self.size,
                'dim': self.image_dim,
                'group': self.group,
                'description': self.description,
            }
        else:
            self.size = new['size']
            self.image_dim = new['dim']
            self.group = new['group']
            self.description = new['description']

    def generate_structure(self, subjects):
        """
        Generate a file detailing which subjects belong in which image
        and their location in the image.

        """
        images = {}
        i = self.next_id

        subjects = subjects.list()
        l = len(subjects)
        w = math.ceil(l/self.size)

        for n in range(w):
            a = n * self.size
            b = min(l, a + self.size)
            subset = subjects[a:b]

            images[i] = Image(i, self.group, subset, None)

            i += 1
        self.next_id = i

        self.images = images
        return images

    def splinter(self, size):
        keys = random.sample(list(self.images), size)
        subset = {k: self.images.pop(k) for k in keys}
        group, next_id = self.load_metadata()
        group = max(self.group+1, group)

        for image in subset.values():
            image.group = group

        splinter = self.__class__(group, subset, next_id)

        meta = self.metadata()
        meta['group'] = group
        splinter.metadata(meta)

        return splinter

    def split_subjects(self, subjects):
        """
        Subdivide a list of subjects into image groups, each of size
        determined in constructor call.
        """
        images = []

        for _ in range(self.permutations):
            keys = subjects.keys()
            random.shuffle(keys)

            length = len(keys)
            w = math.ceil(length/self.size)
            for n in range(w):
                a = n*self.size
                b = min(length, a+self.size)
                subset = keys[a:b]

                images.append(subset)
        return images

    def remove_images(self, images):
        for image in self.iter():
            if image.id in images:
                image.metadata['deleted'] = True

    def upload_subjects(self, path):
        """
        Upload generated images to Panoptes
        """
        uploader = panoptes.Uploader(muon.config.project, self.group)
        existing_subjects = uploader.get_subjects()
        existing_subjects = {k: v for v, k in existing_subjects}

        print('Creating Panoptes subjects')
        for image in self.iter():
            # Skip images that are already uploaded and linked to the
            # subject set, and make sure the zoo_id map is correct
            if image.id in existing_subjects:
                image.zoo_id = existing_subjects[image.id]
                print('Skipping %s' % image)
                continue

            fname = os.path.join(path, 'group_%d' % self.group, image.fname())

            subject = panoptes.Subject()
            subject.add_location(fname)
            subject.metadata.update(image.dump_manifest())

            subject = uploader.add_subject(subject)
            image.zoo_id = subject.id

        print('Uploading subjects')
        uploader.upload()
        self.save_group(True)

    def generate_manifest(self):
        """
        Generate the subject manifest for Panoptes
        """
        raise DeprecationWarning
        fname = muon.data.path('subject_manifest_%d' % self.group)
        keys = list(self.list()[0].dump_manifest().keys())

        with open(fname, 'w') as file:
            writer = csv.DictWriter(file, fieldnames=keys)
            writer.writeheader()

            for image in self.iter():
                writer.writerow(image.dump_manifest())

    def generate_images(self, subjects, path=None):
        """
        Generate subject images to be uploaded to Panoptes
        """
        path = os.path.join(path, 'group_%d' % self.group)
        if not os.path.isdir(path):
            os.mkdir(path)
        for image in self.iter():
            print(image)
            image.plot(self.image_dim, subjects, path)


class Random_Images(Images):
    """
    Creates images of subjects grouped by machine learning cluster.
    Subjects are randomly shuffled within each cluster.
    """

    def generate_structure(self, cluster):
        subjects = cluster.subjects

        images = {}
        i = self.next_id

        for c in range(cluster.config.n_clusters):
            # Skip empty subjects
            if c == 0:
                continue

            subjects = cluster.feature_space.cluster_subjects(c)
            subsets = self.split_subjects(subjects)

            for subset in subsets:
                meta = {
                    'cluster': c,
                }
                images[i] = Image(i, self.group, subset, meta)
                i += 1

        self.next_id = i
        self.images = images
        return images


class MultiGroupImages(Images_Parent):

    def __init__(self, groups):
        images = {}

        for g in groups:
            i = Images.load_group(g)
            images.update(i.images)
        super().__init__(groups, images, None)

    def save_group(self):
        raise Exception('Can\'t save this type of images')

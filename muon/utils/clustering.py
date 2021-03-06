
from muon.utils.subjects import Subjects
from muon.utils.camera import Camera

import numpy as np
import random
from sklearn.decomposition import PCA
from sklearn import preprocessing
import matplotlib.pyplot as plt


class Cluster:

    figure = 0

    def __init__(self, pca, subjects, sample):
        self.pca = pca
        self.subjects = subjects
        self.sample_X = self.project_subjects(sample)

    @classmethod
    def create(cls, subjects, components=8):
        _, charges = subjects.get_charge_array()

        pca = PCA(n_components=components)
        pca.fit(charges)

        sample = subjects.sample(1e4)
        return cls(pca, subjects, sample)

    @classmethod
    def run(cls, subjects):
        cluster = cls.create(subjects)
        cluster.plot()

        import code
        code.interact(local=locals())

    def count_class(self, bound, axis, direction):
        s = self.subjects.list()
        _, X = self.project_subjects(s)

        count = 0
        for item in X:
            if direction == 1:
                if item[axis] > bound:
                    count += 1
            else:
                if item[axis] < bound:
                    count += 1

    def visualize(self):
        camera = Camera()
        fig = plt.figure(figsize=(9, 1))
        fig.subplots_adjust(left=0, right=1, bottom=0, top=1, hspace=.05,
                            wspace=.05)

        count = self.pca.n_components_
        for n in range(count):
            component = self.pca.components_[n, :]
            x, y, c = camera.transform(component)
            ax = fig.add_subplot(1, count+1, n+1, xticks=[], yticks=[])
            ax.scatter(x, y, c=c, s=10, cmap='viridis')

        x, y, c = camera.transform(self.mean_charge())
        ax = fig.add_subplot(1, 1, 1, xticks=[], yticks=[])
        ax.scatter(x, y, c=c, s=10, cmap='viridis')

        plt.show()

    def mean_charge(self):
        subjects = self.subjects.list()
        c = [s.charge for s in subjects]
        c = np.array(c)
        c = np.mean(c, axis=0)
        return c

    def visualize_mean(self):
        camera = Camera()
        fig = plt.figure(figsize=(8, 8))
        fig.subplots_adjust(left=0, right=1, bottom=0, top=1, hspace=.05,
                            wspace=.05)

        x, y, c = camera.transform(self.mean_charge())
        ax = fig.add_subplot(1, 1, 1, xticks=[], yticks=[])
        ax.scatter(x, y, c=c, s=10, cmap='viridis')

        plt.show()

    def plot_subjects(self, subjects, save=False, show=True, **kwargs):
        """
        subjects: list of subject objects
        """
        if subjects is None:
            order, X = self.sample_X
        else:
            order, X = self.project_subjects(subjects)

        sorted_ = {k:[] for k in [-1, 0, 1]}

        fig = kwargs.get('fig', plt.figure())
        subplot = kwargs.get('subplot', (1, 1, 1))
        ax = fig.add_subplot(*subplot)
        for i, s in enumerate(order):
            x, y = X[i, :2]
            label, c = self.subject_plot_label(s)
            sorted_[label].append((x, y, c))

        def plot(v):
            if len(sorted_[v]) > 0:
                x, y, c = zip(*sorted_[v])
                ax.scatter(x, y, c=c, s=2.5)

        for i in [-1, 0, 1]:
            plot(i)

        # ax.axis([-5, 20, -25, 25])
        ax.set_xlim(-5, 15)
        ax.set_ylim(-20, 20)
        ax.set_title('PCA dimensionality reduction of Muon Data')
        ax.set_xlabel('Principle Component 1')
        ax.set_ylabel('Principle Component 2')

        # c = [s.label for s in subjects]
        if save is not None and save is not False:
            if save is True:
                plt.savefig('Figure_%d' % self.figure)
                self.figure += 1
            else:
                plt.savefig(save)
        elif show:
            plt.show()

        return fig, ax

    def subject_plot_label(self, subject_id):
        s = self.subjects[subject_id]
        return s.label, s.color()

    def plot(self, **kwargs):
        return self.plot_subjects(None, **kwargs)

    def plot_all(self, **kwargs):
        return self.plot_subjects(self.subjects.list(), **kwargs)

    def plot_class(self, class_, force_all=False, **kwargs):
        if type(class_) is int:
            class_ = [class_]
        subjects = [s for s in self.subjects.list() if s.label in class_]

        if len(subjects) > 1e4 and not force_all:
            subjects = random.sample(subjects, int(1e4))

        return self.plot_subjects(subjects, **kwargs)

    def download_plotted_subjects(self, x, y, c, size, prefix='', dir_=None):
        subjects = self.subjects_in_range(x, y, c, self.sample_X[0])
        self.download_subjects(subjects, size, prefix, dir_)

    def subjects_in_range(self, x, y, c, subjects=None):
        if subjects is None:
            subjects = self.subjects.list()

        # Remap bounding box coordinates so name doesn't conflict
        x_ = x
        y_ = y

        if type(c) is int:
            c = [c]

        def in_range(x, y):
            """
            Check if coordinates are inside the bounding box
            """
            def check(x, bounds):
                if bounds is None:
                    return True

                min, max = bounds
                if x > min and x < max:
                    return True
                return False

            return check(x, x_) and check(y, y_)

        def check_type(subject):
            """
            Check if subject is in the required class
            """
            if c is None:
                return True
            subject = self.subjects[subject]
            return subject.label in c

        order, X = self.project_subjects(subjects)
        subjects = []
        for i, point in enumerate(X[:,:2]):
            x, y = point
            if in_range(x, y):
                subject = order[i]
                if check_type(subject):
                    subjects.append(subject)

        return subjects

    def download_subjects(self, subjects, size=None, prefix='', dir_=None):
        """
        Download subject images from panoptes

        subjects: list of subject ids
        size: select random sample from list of subjects
        """
        print(len(subjects), size)
        if size is not None and size < len(subjects):
            subjects = random.sample(subjects, size)
        print(len(subjects))
        subjects = [self.subjects[s] for s in subjects]
        Subjects(subjects).download_images(prefix, dir_)

    def subject_images(self, subjects, size=None):
        """
        Get list of scikit-image objects of subject images from panoptes

        subjects: list of subject ids
        size: select random sample from list of subjects
        """
        print(len(subjects), size)
        if size is not None and size < len(subjects):
            subjects = random.sample(subjects, size)
        print(len(subjects))
        subjects = [self.subjects[s] for s in subjects]
        return Subjects(subjects).load_images()

    def project_subjects(self, subjects):
        """
        subjects: list of subjects to project
        """
        order, charges = self.charge_array(subjects)
        X = self.pca.transform(charges)
        return order, X

    @staticmethod
    def charge_array(subjects):
        return Subjects(subjects).get_charge_array()

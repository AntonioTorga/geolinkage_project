import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

class Visualizator:
    def __init__(self, directory_path):
        self.directory_path = directory_path

    def write_matrix_img(self, matrix, name, row_labels=None, column_labels=None, cmap='viridis'
                        , cbar = False, linewidth = 0, title= None, legend = False):

        ax = sns.heatmap(matrix, cmap=cmap, xticklabels=column_labels, yticklabels=row_labels, cbar=cbar,  linewidths=linewidth, linecolor='white')

        if title:
            ax.set_title(title)

        if legend:
            ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))

        x_fontsize = min(10, 300//len(column_labels))
        y_fontsize = min(10, 300//len(row_labels))

        ax.set_xticklabels(ax.get_xticklabels(), fontsize = x_fontsize)
        ax.set_yticklabels(ax.get_yticklabels(), fontsize = y_fontsize)

        figure = ax.get_figure()

        figure.savefig( self.directory_path + '/' + name + '.svg' , format='svg', bbox_inches='tight')

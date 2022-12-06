# CPD_BT
Code for the paper *Detecting Abrupt Changes in Sequential Pairwise Comparison Data*.

To reproduce the experiments:

1. First run data_generation.ipynb to get the data for experiments;
2. Then run the notebooks for each setting according to their names;

Original experiments were run on Google Colab, so there are some commands at the beginning of each note book like:

```
from google.colab import drive
drive.mount('/content/drive')
import os, sys
sys.path.append('/content/drive/MyDrive/CPD_BT')
```

which can be removed if you want to run them locally.

The folder "application" contains the code and data needed to reproduce the real data analysis.

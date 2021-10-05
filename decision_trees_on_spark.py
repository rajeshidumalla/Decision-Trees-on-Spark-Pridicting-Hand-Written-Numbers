# -*- coding: utf-8 -*-
"""Decision Trees on Spark.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1GA9gupC0xD0xTE_ZH1N2ELJ33tlA66yy

# Decision Trees on Spark

Let's setup Spark Colab environment.
"""

!pip install pyspark
!pip install -U -q PyDrive
!apt install openjdk-8-jdk-headless -qq
import os
os.environ["JAVA_HOME"] = "/usr/lib/jvm/java-8-openjdk-amd64"

"""Now I am authenticate a Google Drive client to download the files that I will be processing in Spark job."""

from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from google.colab import auth
from oauth2client.client import GoogleCredentials

# Authenticate and create the PyDrive client
auth.authenticate_user()
gauth = GoogleAuth()
gauth.credentials = GoogleCredentials.get_application_default()
drive = GoogleDrive(gauth)

id='1aJrdYMVmmnUKYhLTlXtyB0FQ9gYJqCrs'
downloaded = drive.CreateFile({'id': id})
downloaded.GetContentFile('mnist-digits-train.txt')

id='1yLwxRaJIyrC03yxqbTKpedMmHEF86AAq'
downloaded = drive.CreateFile({'id': id})
downloaded.GetContentFile('mnist-digits-test.txt')

"""If you executed the cells above, you should be able to see the dataset we will use for this Colab under the "Files" tab on the left panel.

Next, let me import some of the common libraries needed for my task.
"""

# Commented out IPython magic to ensure Python compatibility.
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
# %matplotlib inline

import pyspark
from pyspark.sql import *
from pyspark.sql.types import *
from pyspark.sql.functions import *
from pyspark import SparkContext, SparkConf

"""Let's initialize the Spark context."""

# create the session
conf = SparkConf().set("spark.ui.port", "4050")

# create the context
sc = pyspark.SparkContext(conf=conf)
spark = SparkSession.builder.getOrCreate()

"""You can easily check the current version and get the link of the web interface. In the Spark UI, you can monitor the progress of your job and debug the performance bottlenecks (if your Colab is running with a **local runtime**)."""

spark

"""If you are running this Colab on the Google hosted runtime, the cell below will create a *ngrok* tunnel which will allow you to still check the Spark UI."""

!wget https://bin.equinox.io/c/4VmDzA7iaHb/ngrok-stable-linux-amd64.zip
!unzip ngrok-stable-linux-amd64.zip
get_ipython().system_raw('./ngrok http 4050 &')
!curl -s http://localhost:4040/api/tunnels | python3 -c \
    "import sys, json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])"

"""### Data Loading

![MNIST](https://upload.wikimedia.org/wikipedia/commons/thumb/2/27/MnistExamples.png/220px-MnistExamples.png)

I will be using the famous [MNIST database](https://en.wikipedia.org/wiki/MNIST_database), a large collection of handwritten digits that is widely used for training and testing in the field of machine learning.

The dataset has already been converted to the popular LibSVM format, where each digit is represented as a sparse vector of grayscale pixel values.
"""

training = spark.read.format("libsvm").load("mnist-digits-train.txt")
test = spark.read.format("libsvm").load("mnist-digits-test.txt")

# Cache data for multiple uses
training.cache()
test.cache()

training.show(truncate=False)

training.printSchema()

test.printSchema()

"""First of all, find out how many instances we have in our training / test split."""

print(training.count())
print(test.count())

"""Now train a Decision Tree on the training dataset using Spark MLlib.

I am using the Python example on this documentation page: [https://spark.apache.org/docs/latest/ml-classification-regression.html#decision-tree-classifier](https://spark.apache.org/docs/latest/ml-classification-regression.html#decision-tree-classifier)
"""

# importing the Decision Tree Classifier libraries
from pyspark.ml import Pipeline
from pyspark.ml.classification import DecisionTreeClassifier
from pyspark.ml.feature import StringIndexer, VectorIndexer
from pyspark.ml.evaluation import MulticlassClassificationEvaluator

# defining DecisionTreeClassifier
dt = DecisionTreeClassifier(labelCol="label", featuresCol="features")

# Model fitted by DecisionTreeClassifier.
model = dt.fit(training)

predictions = model.transform(test)

"""With the Decision Tree I just induced on the training data, predict the labels of the test set.
Printing the predictions for the first 10 digits, and comparing them with the labels.
"""

predictions.select("prediction", "label").show(10)

"""The small sample above looks good, but not great!

Let's dig deeper. Computing the accuracy of the model, using the ```MulticlassClassificationEvaluator``` from MLlib.
"""

evaluator = MulticlassClassificationEvaluator(
    labelCol="label", predictionCol="prediction", metricName="accuracy")
accuracy = evaluator.evaluate(predictions)
print("Accuracy = %g " % accuracy)

"""Finding out the max depth of the trained Decision Tree, and its total number of nodes."""

print(model)

"""It appears that the default settings of the Decision Tree implemented in MLlib did not allow us to train a very powerful model!

Before starting to train a Decision Tree, I can tune the max depth it can reach by using the [setMaxDepth()](https://spark.apache.org/docs/latest/api/python/reference/api/pyspark.ml.classification.DecisionTreeClassifier.html#pyspark.ml.classification.DecisionTreeClassifier.setMaxDepth) method. Train 21 different DTs, varying the max depth from 0 to 20, endpoints included (i.e., [0, 20]). For each value of the parameter, I am going to print the accuracy achieved on the test set, and the number of nodes contained in the given DT.

**IMPORTANT:** this parameter sweep can take 30 minutes or more, depending on how busy is your Colab instance. Notice how the induction time grows super-linearly!
"""

def train_dt(training, test, max_depth):
    dt = DecisionTreeClassifier(labelCol="label", featuresCol="features", maxDepth=max_depth)
    model = dt.fit(training)
    predictions = model.transform(test)
    evaluator = MulticlassClassificationEvaluator(
        labelCol="label", predictionCol="prediction", metricName="accuracy")
    accuracy = evaluator.evaluate(predictions)
    return accuracy

accs = []
for d in range(21):
    accs.append(train_dt(training, test, d))

"""Just making some changes to plot the Accuracy of the model"""

y = accs
x = range(0,21)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
y =pd.Series(y)

fig, ax = plt.subplots()
ax.plot(x,y)

def annot_max(x,y, ax=None):
    xmax = x[np.argmax(y)]
    ymax = y.max()
    text= "x={:.3f}, y={:.3f}".format(xmax, ymax)
    if not ax:
        ax=plt.gca()
    bbox_props = dict(boxstyle="square,pad=0.3", fc="w", ec="k", lw=0.72)
    arrowprops=dict(arrowstyle="->",connectionstyle="angle,angleA=0,angleB=60")
    kw = dict(xycoords='data',textcoords="axes fraction",
              arrowprops=arrowprops, bbox=bbox_props, ha="right", va="top")
    ax.annotate(text, xy=(xmax, ymax), xytext=(0.94,0.96), **kw)

annot_max(x,y)


ax.set_ylim(-0.3,1.5)
plt.show()

# Stopping Spark Environment
sc.stop()

"""It appears that the model is performing 88% accuracy at Max_Depth of 16. Actually, not bad :D"""
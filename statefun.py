from extraction import *
from visualization import *
from functools import wraps
from flask import Flask, render_template, Markup
import base64
import logging

classes: List[PyClass] = []
app = Flask(__name__)


def dataflow(cls):
    classes.insert(0, ClassExtraction(cls).get())


def init():
    if len(classes) == 0:
        logging.warning("No classes defined with @dataflow annotation.")
        return

    resolver = ClassDependencyResolver(classes)
    resolver.resolve()


def visualize():
    app.run()


@app.route("/")
def visualize_graph():
    graph = Visualizer(classes).visualize()
    chart_output = graph.pipe(format="svg")

    return render_template("index.html", chart_output=chart_output)


# account = UserAccount()
# TODO
# 1. Types for input (if none is given)
# 2. Types for return types
# 3. Change all code to AST extraction
# 4. Clean up code + add README
# 5. Add fun to fun support
# 6. Make graphviz!

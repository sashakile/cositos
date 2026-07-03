Hi, I was wondering how much work will be porting the "backend" part of anywidget to another language that already has a jupyter kernel. I always miss the ease of throwing a lot of widgets on top of some program to make it more accessible and interactive.
 
I would love to have the possibility of defining a widget and being able to run it from a python notebook or a Julia notebook or even a C# one.
 
Would you think it is something doable? What will be the main challenges or blockers?
 
Hey! I'm very much interested in supporting the reuse of widget front end code for different Jupyter kernels. I have actually implemented support for Deno (https://github.com/manzt/anywidget/tree/main/packages/deno). I'd like to similarly do the same for R.
 
The main blocker are finding a way to avoid anywidget's core taking on responsibility for such bindings. Ideally there is a way to reuse the frontends and allow folks with good knowledge of other language ecosystems to maintain the APIs to send messages over the Jupyter comm and serialize data.
 
Cool, could you point out where that bindings are happening now, so
I can start looking and tinkering.
 
Also, is there some anywidget's doc that you consider important to look at?
 
This is pretty burried in the ipywidgets internals. Ultimately there needs to be some way of representing and emitting state from the kernel over a Jupyter comm using `jupyter.widgets` messages. https://github.com/jupyter-widgets/ipywidgets/blob/main/packages/schema/messages.md
 
For the deno internals, I wrote a wrapper around the `Deno.jupyter.broadcast` API which let's me send those Jupyter messages: https://github.com/manzt/anywidget/blob/main/packages/deno/src/mod.ts#L89-L152
 
On the Python side, we have been working on rewriting the anywidget internals to be a thin layer on top of the `comm` library with out descriptor based API: https://github.com/manzt/anywidget/blob/main/anywidget/_descriptor.py
 
We have written up some of this in the docs: https://anywidget.dev/en/experimental/
Experimental Features | anywidget
Experimental Features and APIs
 
But overall, it was a lot of reverse engineering how ipywidgets works. Hopefully our reimplementation in Python and Deno-implemention help.
 
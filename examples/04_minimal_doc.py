import sys, json
sys.path.insert(0, r'C:\Users\tglaubach\repos\pydocmaker\src')

import pydocmaker as pyd

print(pyd.__file__)
print(pyd.__version__)

doc = pyd.Doc()

content = """## Some Example Text

One morning, when Gregor Samsa woke from troubled dreams, he found himself *transformed* in his bed into a horrible  [vermin](http://en.wikipedia.org/wiki/Vermin "Wikipedia Vermin"). He lay on his armour-like back, and if he lifted his head a little he could see his brown belly, slightly domed and divided by arches into stiff sections. The bedding was hardly able to cover **strong** it and seemed ready to slide off any moment. His many legs, pitifully thin compared with the size of the rest of him, link waved abouthelplessly as he looked. <cite>“What's happened to me?”</cite> he thought. It wasn't a dream. His room, a proper human room although a little too small, lay peacefully between its four familiar walls.</p>

### The bedding was hardly able to cover it.

It showed a lady fitted out with a fur hat and fur boa who sat upright, raising a heavy fur muff that covered the whole of her lower arm towards the viewer a solid fur muff into which her entire forearm disappeared..

#### Things we know about Gregor's sleeping habits.

- He always slept on his right side.
- He has to get up early (to start another dreadful day).
- He has a drawer and a alarm clock next to his bed.
- His mother calls him when he gets up to late.

"""

doc.add_md(content)
doc.add_md("First he wanted to stand up quietly and undisturbed, get dressed, above all have breakfast, and only then consider further action, for (he noticed this clearly) by thinking things over in bed he would not reach a reasonable conclusion. He remembered that he had already often felt a light pain or other in bed, perhaps the result of an awkward lying position, which later turned out to be purely imaginary when he stood up, and he was eager to see how his present fantasies would gradually dissipate. That the change in his voice was nothing other than the onset of a real chill, an occupational illness of commercial travelers, of that he had not the slightest doubt.")
doc.add_md("## Formatting and Images")
doc.add("this is how to embed preformatted text via a verbatim part")
doc.add_pre("""
function metamorphose(protagonist,author){
    if( protagonist.name.first === 'Gregor' && author.name.last === 'Kafka' ){
        protagonist.species = 'insect';
    }
}
""")
doc.add_tex("\\textit{This is some dummy LaTeX text.}")

doc.add_md("this is how to embed a table:")

header = ['Name', 'Age', 'City']
table = [
    ['John Doe', "30", 'New York'],
    ['Jane Smith', "25", 'Los Angeles'],
    ['Mike Johnson', "35", 'Chicago']
]
doc.add_table(table, header=header, borders=True, caption='This is my example table')

doc.add('And this is how to embed an Image:')
doc.add_image(image="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEYAAAAUCAAAAAAVAxSkAAABrUlEQVQ4y+3TPUvDQBgH8OdDOGa+oUMgk2MpdHIIgpSUiqC0OKirgxYX8QVFRQRpBRF8KShqLbgIYkUEteCgFVuqUEVxEIkvJFhae3m8S2KbSkcFBw9yHP88+eXucgH8kQZ/jSm4VDaIy9RKCpKac9NKgU4uEJNwhHhK3qvPBVO8rxRWmFXPF+NSM1KVMbwriAMwhDgVcrxeMZm85GR0PhvGJAAmyozJsbsxgNEir4iEjIK0SYqGd8sOR3rJAGN2BCEkOxhxMhpd8Mk0CXtZacxi1hr20mI/rzgnxayoidevcGuHXTC/q6QuYSMt1jC+gBIiMg12v2vb5NlklChiWnhmFZpwvxDGzuUzV8kOg+N8UUvNBp64vy9q3UN7gDXhwWLY2nMC3zRDibfsY7wjEkY79CdMZhrxSqqzxf4ZRPXwzWJirMicDa5KwiPeARygHXKNMQHEy3rMopDR20XNZGbJzUtrwDC/KshlLDWyqdmhxZzCsdYmf2fWZPoxCEDyfIvdtNQH0PRkH6Q51g8rFO3Qzxh2LbItcDCOpmuOsV7ntNaERe3v/lP/zO8yn4N+yNPrekmPAAAAAElFTkSuQmCC")

doc.update_meta(author='Me')

doc.to_pdf('template_example.pdf')


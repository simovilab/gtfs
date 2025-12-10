import os
import ontospy
from ontospy.gendocs.viz.viz_html_single import HTMLVisualizer
from ontospy.gendocs.viz.viz_html_multi import KompleteVizMultiModel


# Define input files
ontology_files = [
    "ontologies/schedule.ttl",
    "ontologies/i18n/en.ttl",
    "ontologies/i18n/es.ttl"
]

# Ensure docs directory exists
output_dir = "docs"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

print(f"Loading ontologies: {ontology_files}")

# Load ontologies
# Ontospy constructor accepts a uri or a file path. 
# For multiple files, we usually load the first and then scan/import others, 
# or we can pass a list if the API supports it, or instantiate one and merge.
# Looking at Ontospy API, it usually takes a single URI argument. 
# However, we can use rdflib to merge them first or load them sequentially.

# Let's try loading the main one and then importing others if Ontospy supports easy merging.
# Actually, Ontospy(uri) loads that URI.
# A robust way is to use rdflib to parse all files into a graph, then pass that graph to Ontospy (if supported)
# or simply let Ontospy load them. 

# Let's try loading the main file.
g = ontospy.Ontospy(ontology_files[0], verbose=True)

# Load additional files
for f in ontology_files[1:]:
    print(f"Loading {f}...")
    g.rdflib_graph.parse(f, format="turtle")

# Re-scan the graph to update internal indices after adding more triples
print("Scanning graph...")
g.build_all()

print("Generating documentation...")

# Create visualizer - Multi-page (KompleteVizMulti) is often the default/best for 'gendocs'
# Using the theme requested: bootwatch-darkly
viz = KompleteVizMultiModel(g, theme="bootwatch-darkly")
viz.build(output_dir)

print(f"Documentation generated in {output_dir}")

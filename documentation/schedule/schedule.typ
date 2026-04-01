#set text(font: "PT Sans")
#show title: set text(size: 19pt)
#show title: set align(center)
#show link: underline

#let reference(contents) = {
  [

    #title[#contents.name]

    *Revised October 28, 2025. See #link(contents.revision_history_url)[Revision History] for more details.*

    #contents.description

    = Document Conventions

    #contents.document_conventions.description

    == Term Definitions

    #contents.document_conventions.term_definitions.description

  ]

  for (term, definition) in contents.document_conventions.term_definitions.terms {
    [/ #term: #definition]
  }

  [

    == Presence

    #contents.document_conventions.presence.description

  ]

  for (name, definition) in contents.document_conventions.presence.conditions {
    [/ #name: #definition]
  }

  [

    == Field Types

    #contents.document_conventions.field_types.description

  ]

  for (name, definition) in contents.document_conventions.field_types.types {
    [/ #name: #definition]
  }

  [

    == Field Signs

    #contents.document_conventions.field_signs.description

  ]

  for (name, definition) in contents.document_conventions.field_signs.signs {
    [/ #name: #definition]
  }

  [

    == Dataset Attributes

    #contents.document_conventions.dataset_attributes.description

  ]

  for (name, definition, example) in contents.document_conventions.dataset_attributes.attributes {
    [/ #name: #definition \ #emph[Example: #example]]
  }

  [

    = Dataset Files

    #contents.dataset_files.description

    #table(
      columns: 3,
      stroke: (x: none),
      table.header[*File Name*][*Presence*][*Description*],
      ..for (name, presence, description) in contents.dataset_files.files {
        (name, presence, description)
      },
    )
  ]
}

#reference(
  yaml("../serializers/schedule.yaml"),
)

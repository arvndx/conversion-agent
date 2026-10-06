import { groupFields } from './fieldMeta.js'

// Lays the fields out in titled groups of one- and two-column tiles. `children(field)` renders one
// tile; `field.wide` says whether it spans the row.
function FieldGroups({ fields, children }) {
  return groupFields(fields).map((g) => (
    <section key={g.id} className="pf-group">
      <h4 className="pf-group__title"><span aria-hidden="true">{g.icon}</span>{g.label}</h4>
      <div className="pf-grid">{g.fields.map((f) => children(f))}</div>
    </section>
  ))
}

export default FieldGroups

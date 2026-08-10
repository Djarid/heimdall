# Heimdall — Norse Mythology Glossary

Every component in the Heimdall architecture takes its name from Norse
mythology, chosen so the myth mirrors the technical role. This glossary gives
the mythological source, its meaning, and the architectural mapping for each
term.

---

## Heimdall

**Myth:** Heimdallr, the watchman of the gods. He guards Bifröst, the bridge
between the mortal world and Asgard. He possesses senses so acute he can hear
grass growing and see for a hundred leagues by day or night; he needs less
sleep than a bird. At Ragnarök he sounds Gjallarhorn to wake the gods. He is
the boundary's guardian: nothing crosses without him seeing it.

**Architecture:** The overall system. The guardian that stands at the boundary
between the untrusted world and the trusted domain, sees and hears everything
that attempts to cross, and controls what passes.

---

## Bifröst

**Myth:** The burning rainbow bridge connecting Midgard (the mortal world) to
Asgard (the realm of the gods). It is the only crossing between the realms, and
Heimdall guards its Asgard end. Strong as it is, it is destined to break under
the weight of invaders at Ragnarök.

**Architecture:** The **taint boundary**. The single crossing point through
which all external content — of any medium — must pass. Everything crossing
Bifröst is marked tainted. Nothing crosses raw.

---

## Himinbjörg

**Myth:** "Heaven's Castle" or "Heaven's Cliffs." Heimdall's hall, situated at
the very edge of Asgard where Bifröst meets the heavens. From here he keeps his
watch over the bridge.

**Architecture:** The **gateway process**. The central component that sits at
the boundary, owns the control channel exclusively, constructs agent context
from the world model, and validates every proposal before execution. Where the
watch is kept.

---

## Mímisbrunnr

**Myth:** Mímir's Well, the well of wisdom and knowledge that lies among the
roots of Yggdrasil. Odin sacrificed one of his eyes for a single drink from it.
All deep knowledge flows from this well.

**Architecture:** The **world model**. The persistent typed graph that is the
authoritative store of everything Heimdall knows. Agents do not hold their own
knowledge; they draw a constructed view from this well. (See also **Mímir**.)

---

## Mímir

**Myth:** The wisest of beings, guardian of Mímisbrunnr. After his beheading,
Odin preserved Mímir's head and consulted it for counsel. Knowledge personified;
the keeper of the well.

**Architecture:** Used in the naming lineage of the world model
(Mímisbrunnr = Mímir's well). The LLMs consulting the world model are, in the
mythological frame, Odin consulting Mímir — the god of wisdom does not *own* the
knowledge, he *asks* the keeper of the well.

---

## Nornir (the Norns)

**Myth:** The three fate-weavers — Urðr (what has become), Verðandi (what is
becoming), and Skuld (what shall be) — who sit at the Well of Urðr beneath
Yggdrasil and shape the destiny of gods and men. Crucially, the Norns do not
*predict* fate; they *set* it. Their weaving is deterministic and binding.

**Architecture:** The **symbolic classifier and reasoner**. A deterministic
rule engine, not an LLM. It maps assertions to typed ontology nodes and derives
new facts by forward-chaining. Like the Norns, it does not guess — it
determines. Its output is fixed by its rules.

---

## Ørlög

**Myth:** "Primal law" or "that which is laid down" (ór + lög, the primordial
layer of what has been ordained). In Norse cosmology ørlög is the foundational
stratum of fate — the laid-down law that underlies existence. The Norns do not
invent fate freely; they weave it *from* ørlög, the given ground that
determines how things must unfold. It is the substrate of destiny, prior to and
beneath the weaving.

**Architecture:** The **configuration substrate**. The defining source from
which all agent behaviour is shaped: the roster, the rules, the plugins, the
prompts, the deterministic controls, and the probabilistic processes. Ørlög is
the laid-down law that Nornir reasons *within* — it defines what the agents are
and how they may behave, and everything downstream is woven from it. Where
Nornir is the weaver, Ørlög is what is woven from. (This component originates
from prior work developed under the internal codename that has been superseded
by this name; it defines the opencode-level configuration Heimdall runs on.)

---

## Gjallarhorn

**Myth:** "The Resounding Horn." Heimdall's horn, whose blast can be heard
throughout all nine realms. Heimdall sounds it to warn the gods of the onset of
Ragnarök — the alarm that signals the boundary has been breached.

**Architecture:** The **alert and escalation mechanism**. Fires on instruction
patterns, constraint violations, taint-boundary breach attempts, canary
failures, and anomalies. The alarm heard across the whole system when something
attempts to cross that should not.

---

## Huginn

**Myth:** One of Odin's two ravens. Huginn means "Thought." Each day Odin sends
Huginn and Muninn out across the world; they return at evening to whisper what
they have seen into his ears. Huginn is Odin's reach into what is happening now.

**Architecture:** The **behavioural observation** half of the introspection
framework. Captures all agent behaviour as structured episodes in real time,
watches Fenrir emissions for injection attempts, and detects drift and anomaly.
Odin's eyes on the present.

---

## Muninn

**Myth:** Odin's second raven. Muninn means "Memory." Where Huginn carries
thought, Muninn carries memory — the accumulated record of what has been seen.
Odin's reach into what has happened.

**Architecture:** The **episode memory** half of the introspection framework.
The structured persistent store of all captured episodes, queryable for
baselines, longitudinal analysis, and cross-agent comparison. Odin's memory of
the past.

---

## Odin

**Myth:** The Allfather, chief of the Aesir. God of wisdom, war, and knowledge.
He sacrificed an eye at Mímir's well and hung himself on Yggdrasil for nine
nights to win the runes. He sends out Huginn and Muninn and receives their
reports; he sees much but acts through counsel and craft rather than brute
force.

**Architecture:** The **roster agent**. A meta-level agent that consumes the
reports of Huginn and Muninn and proposes improvements to agent definitions,
controls, and ontology. Like Odin, it gathers and counsels — but in Heimdall it
may only *propose*; it never executes its own changes. All proposals require
human approval.

---

## Hliðskjálf

**Myth:** Odin's high seat in Asgard, from which he can see into all nine realms
and observe everything that happens across the cosmos. The ultimate vantage
point; nothing escapes the view from Hliðskjálf.

**Architecture:** The **audit framework**. The tamper-evident, signed,
append-only log of every decision, promotion, denial, and escalation. The seat
from which the entire system's history can be seen and reconstructed. Nothing
that happens escapes the record.

---

## Fenrir

**Myth:** The monstrous wolf, child of Loki, so powerful the gods feared him.
Unable to defeat him directly, they bound him — twice he broke ordinary
fetters, so the gods had a deceptively slender ribbon forged that held him
fast where brute chains had failed. Fenrir is power that cannot be destroyed,
only constrained.

**Architecture:** The **sandbox agent**. The only agent permitted to read
tainted content directly. Powerful and permitted to engage with dangerous
material — but bound: no tools, no external network egress, no filesystem,
fresh context each time, under constant introspection. Power that is not
eliminated but constrained.

---

## Gjöll

**Myth:** The river that borders Helheim, the realm of the dead. It is spanned
by Gjallarbrú, a bridge roofed with shining gold and guarded by the maiden
Móðguðr, who challenges all who attempt to cross and demands they account for
themselves. The dead must cross Gjöll to enter Hel; the living who attempt it
are questioned closely.

**Architecture:** The **value-integrity and action-time re-validation layer**.
The boundary an action-critical value must cross — under scrutiny — before it
can parameterise a consequential action. Like Gjallarbrú's guardian, Gjöll
challenges each value: re-derive it, satisfy the constraint, prove promotion,
show independent provenance. Nothing action-critical crosses unquestioned.

---

## Yggdrasil

**Myth:** The World Tree, the immense ash whose branches and roots bind together
all nine realms of the cosmos. Everything is connected through Yggdrasil; it is
the structure within which all existence is arranged.

**Architecture:** The **ontology framework** (future). The connecting structure
of types and relations within which all of Heimdall's knowledge is arranged and
made navigable. The tree that binds the realms of knowledge into one structure.

---

## Ragnarök *(referenced concept)*

**Myth:** The foretold end — the great battle in which the gods fall, Bifröst
breaks under the invading host, Fenrir breaks free, and the world is consumed
before its renewal. The moment the boundary fails and the bound powers are
loosed.

**Architecture:** Used conceptually to denote **total boundary failure** — the
assumed-breach scenario in which the trust roots themselves are compromised.
Heimdall's design accepts that against a sufficiently resourced adversary this
is possible; the architecture's job is to make it costly, loud, and
reconstructable, not to pretend it cannot occur.

---

## Naming lineage at a glance

| Term | Domain | Role |
|------|--------|------|
| **Heimdall** | The watchman | The system |
| **Bifröst** | The bridge he guards | Taint boundary |
| **Himinbjörg** | His hall at the bridge | Gateway process |
| **Mímisbrunnr** | The well of wisdom | World model |
| **Mímir** | Keeper of the well | (world model lineage) |
| **Nornir** | The fate-weavers | Symbolic reasoner |
| **Ørlög** | The primal law fate is woven from | Configuration substrate (roster, rules, plugins, controls, processes) |
| **Gjallarhorn** | Heimdall's alarm horn | Alert / escalation |
| **Huginn** | Odin's raven, Thought | Behavioural observation |
| **Muninn** | Odin's raven, Memory | Episode memory |
| **Odin** | Receiver of the ravens | Roster agent |
| **Hliðskjálf** | Odin's all-seeing seat | Audit framework |
| **Fenrir** | The bound wolf | Sandbox agent |
| **Gjöll** | The guarded river-crossing | Value integrity gate |
| **Yggdrasil** | The world tree | Ontology framework (future) |
| **Ragnarök** | The end / boundary failure | Assumed-breach scenario |

---

*Heimdall specification and documentation licensed under CC-BY-SA-4.0.
See LICENSE.md.*

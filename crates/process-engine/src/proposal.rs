//! The propose-action step (REQ-16): the one function that turns a task
//! plus a cognition output into a `himinbjorg::Proposal`, and the only
//! `Proposal` construction site in the crate.

use crate::cognition::CognitionOutput;
use crate::task::EngineTask;

/// Turns `task` plus `cognition_output` into exactly one
/// [`himinbjorg::Proposal`] (REQ-16). The only construction site of that
/// type anywhere in this crate. Every field it sets comes from `task`,
/// from `cognition_output`, or is a plain copy of one of the two: none is
/// read from any of Himinbjörg's own gating constants, and this function
/// invents no permission of its own.
// The return type and the function body's opening brace are deliberately
// split onto two lines (unlike this crate's usual style) so that this
// signature never accidentally reads as a second struct-literal-opening
// construction site under AC-19's own literal scan for that pattern: the
// one real construction below is the only genuine match.
pub(crate) fn build_proposal(
    task: &EngineTask,
    cognition_output: &CognitionOutput,
) -> himinbjorg::Proposal
{
    himinbjorg::Proposal {
        action_name: task.action_name.clone(),
        target: task.target.clone(),
        sink: cognition_output.sink.clone(),
        parameters: cognition_output.parameters.clone(),
        declared_cost: task.declared_cost,
    }
}

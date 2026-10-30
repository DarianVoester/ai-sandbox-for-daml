# Lesson 1: Authorization & the Propose-Accept Pattern

## Theory: Signatories and Bilateral Contracts
In Daml, no contract (`Template`) can be created on the Canton ledger without the explicit authorization of all `signatory` parties. If an `Asset` template specifies both `issuer` and `owner` as `signatory`, a direct `createCmd Asset` submitted by a single party will fail with a missing authorization error.

## Solution Pattern: Propose-Accept
To safely instantiate a bilateral contract with mutual consent, the workflow is split into two atomic transactions:
1. **Proposal:** The `issuer` creates an `AssetProposal` contract (where only `issuer` is `signatory`, and `owner` is `observer`).
2. **Acceptance:** The `owner` exercises a consuming choice `Accept` on the `AssetProposal` (`controller owner`). Inside the choice body, both the authorization of the `issuer` (carried via the proposal's signatory) and the `owner` (via the choice controller) are present, allowing `create Asset` to succeed.

## Exercise
In `workspace/daml/Main.daml`, add the choice `Accept : ContractId Asset` controlled by `owner` to the `AssetProposal` template. Then update the `setup` script so that `bob` exercises the `Accept` choice on `proposalCid`.

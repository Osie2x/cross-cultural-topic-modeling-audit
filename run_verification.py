"""Run saved-output checks against a locally held evidence directory."""
import argparse
import json
from pathlib import Path
import pandas as pd
from verification_code import source_checks, verify_runs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('results', type=Path)
    parser.add_argument('reference', type=Path)
    parser.add_argument('comparison_ids', type=Path)
    args = parser.parse_args()
    reference = pd.read_csv(args.reference).set_index('ID_noNA_Dup')
    ids = pd.Index(pd.read_csv(args.comparison_ids)['ID_noNA_Dup'])
    if not reference.index.is_unique or not ids.is_unique or ids.hasnans:
        raise ValueError('IDs must be nonmissing and unique')
    if not ids.isin(reference.index).all():
        raise ValueError('Comparison IDs absent from reference')
    source_checks(args.evidence)
    verified, _, _ = verify_runs(pd.read_csv(args.results), args.evidence, reference, ids)
    print(json.dumps({'verified_completed_runs': len(verified), 'checks_passed': True}))


if __name__ == '__main__':
    main()

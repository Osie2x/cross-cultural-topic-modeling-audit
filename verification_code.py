"""Selected verification functions from a completed reproducibility audit.

The comparison and verification functions are preserved from the working audit.
Private inputs, model code and research outputs are not distributed.
"""
from pathlib import Path
import hashlib, json
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

def find_file(root,name):
    root=Path(root)
    direct=[root/name,root/'frozen_inputs'/name,root/'round2_bundle'/name]
    for p in direct:
        if p.is_file(): return p
    matches=list(root.rglob(name))
    if not matches: raise FileNotFoundError(name)
    return sorted(matches,key=lambda p:len(p.parts))[0]


def source_checks(evidence):
    manifest=json.loads(find_file(evidence,'manifest.json').read_text())
    rows=[]
    for name,wanted in manifest['files'].items():
        p=find_file(evidence,name);actual=hashlib.sha256(p.read_bytes()).hexdigest()
        rows.append({'file':name,'sha256':actual,'matches_saved_hash':actual==wanted})
    result=pd.DataFrame(rows)
    assert result.matches_saved_hash.all()
    return result


def choose2(a):
    a=np.asarray(a,dtype=float)
    return float(np.sum(a*(a-1)/2))


def compare(reference,rerun,ids):
    a=reference.loc[ids,'Topic'].astype(int);b=rerun.loc[ids,'Topic'].astype(int)
    table=pd.crosstab(a.rename('reference_topic'),b.rename('rerun_topic'))
    ri,ci=linear_sum_assignment(-table.to_numpy())
    matched=int(table.to_numpy()[ri,ci].sum());n=len(ids)
    cells=choose2(table.to_numpy());rowpairs=choose2(table.sum(axis=1));colpairs=choose2(table.sum(axis=0))
    allpairs=n*(n-1)/2;expected=rowpairs*colpairs/allpairs;maximum=(rowpairs+colpairs)/2
    ari=(cells-expected)/(maximum-expected) if maximum!=expected else 1.0
    mapping=pd.DataFrame({'reference_topic':table.index[ri],'rerun_topic':table.columns[ci],'matched_n':table.to_numpy()[ri,ci]})
    return {'shared_n':n,'matched_n':matched,'agreement_percent':100*matched/n,'ARI':ari},table,mapping


def assignments(evidence,row,stage='after'):
    value=row[f'assignment_{stage}_file']
    return pd.read_csv(find_file(evidence,Path(value).name)).set_index('ID_noNA_Dup')


def verify_runs(results,evidence,reference,ids):
    rows=[];tables={};mappings={}
    for _,row in results.loc[results.status=='completed'].iterrows():
        after=assignments(evidence,row);before=assignments(evidence,row,'before')
        assert after.index.is_unique and before.index.equals(after.index)
        metric,table,mapping=compare(reference,after,ids)
        assert metric['matched_n']==int(row.matched_n)
        assert abs(metric['agreement_percent']-float(row.agreement_percent))<1e-9
        assert abs(metric['ARI']-float(row.ARI))<1e-10
        assert int(before.Topic.eq(-1).sum())==int(row.outliers_before)
        assert after.Topic.nunique()==int(row.topics_after) and not after.Topic.eq(-1).any()
        probabilities=np.load(find_file(evidence,Path(row.probabilities_file).name),allow_pickle=False)
        assert probabilities.shape==(len(before),before.Topic[before.Topic!=-1].nunique()) and np.isfinite(probabilities).all()
        expected=before.Topic.to_numpy().copy();mask=expected==-1
        expected[mask]=probabilities[mask].argmax(axis=1)
        assert np.array_equal(expected,after.Topic.to_numpy())
        if int(row['round'])==2:
            initial=pd.read_csv(find_file(evidence,f'{row.run_id}_initial_hdbscan.csv')).set_index('ID_noNA_Dup')
            assert initial.index.equals(after.index)
            assert initial.Topic[initial.Topic!=-1].nunique()==int(row.initial_clusters)
            assert initial.Topic.nunique()==int(row.initial_labels_including_outlier)
            assert int(initial.Topic.eq(-1).sum())==int(row.initial_outliers)
        upper=100*table.sum(axis=0).nlargest(min(len(table.index),len(table.columns))).sum()/len(ids)
        if pd.notna(row.size_only_upper_bound_percent):assert abs(upper-float(row.size_only_upper_bound_percent))<1e-9
        rows.append(dict(run_id=row.run_id,round=int(row['round']),**metric,all_assignment_rows=len(after),outliers_before=int(before.Topic.eq(-1).sum()),topics_after=after.Topic.nunique(),probability_reassignment_verified=True,initial_counts_verified=int(row['round'])==2))
        tables[row.run_id]=table;mappings[row.run_id]=mapping
    return pd.DataFrame(rows),tables,mappings

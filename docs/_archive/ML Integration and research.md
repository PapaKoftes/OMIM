# ML Integration & Research Strategy

Version: v0.1.0  

See also: [[Full System Architecture]], [[Manufacturing Geometry Graph (MGG) Specification]], [[Benchmarking]], [[Dataset and Research Infrastructure]]

---

## ML Positioning Statement

**OMIM is not an "AI system."** It is a deterministic manufacturing intelligence infrastructure that includes ML as one optional, bounded layer.

The demo should never say:
- "AI-powered manufacturability analysis"
- "Intelligent manufacturing AI"
- "Smart CNC planning"
- "AI detects manufacturing features"

The demo should say:
- "Rule-based manufacturability validation with ML-assisted semantic annotation"
- "Deterministic validation pipeline with optional GNN feature classification"
- "Manufacturing geometry graph with confidence-annotated feature inference"

This framing matters for:
1. Scientific credibility — reviewers will reject overclaiming
2. Hackathon judges — researchers appreciate honesty about what ML can/can't do
3. Long-term trust — systems that overclaim get discredited when they fail

The interesting result is NOT "the AI works." The interesting result is: **"we built infrastructure that makes it possible to measure whether it works."**

---

## ML Philosophy

ML is a secondary system in OMIM. Its role is precisely defined:

| ML MAY | ML MUST NEVER |
|--------|---------------|
| Infer semantic feature classes | Override geometric measurements |
| Rank competing hypotheses | Claim certainty about ambiguous cases |
| Estimate classification confidence | Contradict deterministic validation results |
| Assist with anomaly detection | Fabricate manufacturing rules |
| Learn from synthetic labeled data | Redefine what "manufacturable" means |

If there is a conflict between an ML output and a deterministic validation result, **the deterministic result is authoritative**.

---

## Where ML Fits in the Pipeline

```
DXF → Parser → MGG Builder → Validation Engine → Semantic Layer
                                                      ↑
                                         [ML assists here only]
```

ML operates AFTER validation, not before. It annotates the MGG with semantic hypotheses, it does not validate or modify the underlying geometry.

---

## ML Task 1: Feature Classification (BENCH-001)

### Model Architecture: GraphSAGE

**Reference**: Hamilton, W.L., Ying, R., Leskovec, J. "Inductive Representation Learning on Large Graphs." NeurIPS 2017. [arXiv:1706.02216](https://arxiv.org/abs/1706.02216)

GraphSAGE is chosen because:
1. **Inductive**: Can generalize to unseen panels at inference (no retraining needed)
2. **Efficient**: Neighbor sampling scales to large graphs
3. **Well-understood**: Stable, reproducible, widely cited baseline
4. **Appropriate for v0**: More advanced architectures (GIN, GPS-Transformer) are premature

```python
# omim/ml/models/gnn_classifier.py

import torch
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv, BatchNorm

class ManufacturingFeatureGNN(torch.nn.Module):
    """
    GraphSAGE-based manufacturing feature classifier.
    
    Input: Manufacturing Geometry Graph nodes with geometric features
    Output: Feature class probabilities per node
    
    Reference: Hamilton et al., NeurIPS 2017 (arXiv:1706.02216)
    """
    
    def __init__(
        self,
        in_channels: int,      # input feature dimensionality
        hidden_channels: int = 128,
        out_channels: int = 13,  # number of feature classes in ontology
        num_layers: int = 3,
        dropout: float = 0.3,
    ):
        super().__init__()
        self.num_layers = num_layers
        self.dropout = dropout
        
        self.convs = torch.nn.ModuleList()
        self.norms = torch.nn.ModuleList()
        
        # Input layer
        self.convs.append(SAGEConv(in_channels, hidden_channels))
        self.norms.append(BatchNorm(hidden_channels))
        
        # Hidden layers
        for _ in range(num_layers - 2):
            self.convs.append(SAGEConv(hidden_channels, hidden_channels))
            self.norms.append(BatchNorm(hidden_channels))
        
        # Output layer
        self.convs.append(SAGEConv(hidden_channels, out_channels))
    
    def forward(self, x, edge_index):
        for i, (conv, norm) in enumerate(zip(self.convs[:-1], self.norms)):
            x = conv(x, edge_index)
            x = norm(x)
            x = F.relu(x)
            x = F.dropout(x, p=self.dropout, training=self.training)
        
        x = self.convs[-1](x, edge_index)
        return x  # raw logits; apply softmax for probabilities
    
    def predict_proba(self, x, edge_index):
        return F.softmax(self.forward(x, edge_index), dim=-1)
```

### Node Feature Vector

Each geometry node is represented as a fixed-size feature vector:

```python
# omim/ml/graph_converter.py

def geometry_node_to_features(node: GeometryNode) -> list[float]:
    """
    Convert a GeometryNode to a fixed-size feature vector for GNN input.
    
    Feature vector (dimension: 16):
    [0]  area_normalized        # area / max_area (0-1)
    [1]  perimeter_normalized   # perimeter / max_perimeter (0-1)
    [2]  aspect_ratio           # bounding_box_width / bounding_box_height (log-scaled)
    [3]  circularity            # 4π·area / perimeter² (0-1, 1.0 = perfect circle)
    [4]  diameter_normalized    # diameter / 100mm (for circles; 0 for non-circles)
    [5]  is_circle              # binary: 1.0 if circle entity
    [6]  is_closed              # binary: 1.0 if closed contour
    [7]  is_outer_boundary      # binary: 1.0 if panel outer boundary
    [8]  centroid_x_normalized  # x_centroid / panel_width (0-1)
    [9]  centroid_y_normalized  # y_centroid / panel_height (0-1)
    [10] layer_cut              # one-hot: CUT layer
    [11] layer_drill            # one-hot: DRILL layer
    [12] layer_pocket           # one-hot: POCKET layer
    [13] layer_other            # one-hot: other layer
    [14] n_contained_features   # number of features geometrically inside this node (normalized)
    [15] distance_to_edge_norm  # distance to nearest panel edge / panel_size (0-1)
    """
```

### Training Protocol

```python
# omim/ml/trainer.py

class GNNTrainer:
    def __init__(
        self,
        model: ManufacturingFeatureGNN,
        optimizer_lr: float = 0.001,
        weight_decay: float = 1e-4,
        max_epochs: int = 100,
        early_stopping_patience: int = 15,
        class_weights: torch.Tensor | None = None,  # for imbalanced classes
        device: str = "auto",
    ):
    
    def train(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader,
        checkpoint_dir: str,
    ) -> TrainingResult:
        """
        Training loop with early stopping.
        
        Loss: Cross-entropy with class weights (to handle SHELF_PIN_HOLE dominance)
        Optimizer: Adam with weight decay
        Scheduler: ReduceLROnPlateau on val macro F1
        
        Logging: loss + macro F1 per epoch
        """
```

### Class Imbalance Handling

In the default feature distribution, SHELF_PIN_HOLE dominates (~40% of all holes). Handle this with:

```python
# Inverse frequency weighting
from sklearn.utils.class_weight import compute_class_weight

class_weights = compute_class_weight(
    class_weight="balanced",
    classes=numpy.unique(y_train),
    y=y_train
)
class_weights_tensor = torch.FloatTensor(class_weights)
criterion = torch.nn.CrossEntropyLoss(weight=class_weights_tensor)
```

---

## ML Task 2: Manufacturability Validation (BENCH-002)

### Why ML for Validation?

The deterministic rule engine IS the ground truth. The ML model for BENCH-002 is a research question:
> **Can a GNN learn to detect manufacturing violations without explicit rule programming?**

If yes: suggests GNNs can learn manufacturing rules from data.
If no: validates that rule-based systems are necessary for this domain.

### Model Architecture: Graph-level Binary Classifier

```python
class ManufacturabilityGNN(torch.nn.Module):
    """
    Graph-level binary classifier: is the panel manufacturable?
    
    Uses global pooling to aggregate node embeddings into graph embedding.
    """
    
    def __init__(self, in_channels, hidden_channels=128):
        super().__init__()
        self.conv1 = SAGEConv(in_channels, hidden_channels)
        self.conv2 = SAGEConv(hidden_channels, hidden_channels)
        self.conv3 = SAGEConv(hidden_channels, hidden_channels)
        self.classifier = torch.nn.Sequential(
            torch.nn.Linear(hidden_channels * 2, hidden_channels),
            torch.nn.ReLU(),
            torch.nn.Dropout(0.3),
            torch.nn.Linear(hidden_channels, 1),
        )
    
    def forward(self, x, edge_index, batch):
        x = F.relu(self.conv1(x, edge_index))
        x = F.relu(self.conv2(x, edge_index))
        x = self.conv3(x, edge_index)
        
        # Global mean + max pooling
        x_mean = global_mean_pool(x, batch)
        x_max = global_max_pool(x, batch)
        x_global = torch.cat([x_mean, x_max], dim=1)
        
        return self.classifier(x_global).squeeze(-1)
```

---

## ML Task 3: Anomaly Detection (BENCH-004)

### Approach: Graph Autoencoder

**Reference**: Kipf, T.N., Welling, M. "Variational Graph Auto-Encoders." NIPS Workshop 2016. [arXiv:1611.07308](https://arxiv.org/abs/1611.07308)

Train on valid panels only. Anomaly score = reconstruction error for each node.

```python
from torch_geometric.nn import GAE, VGAE, GCNConv

class VariationalManufacturingEncoder(torch.nn.Module):
    def __init__(self, in_channels, hidden_channels, out_channels):
        super().__init__()
        self.conv1 = GCNConv(in_channels, hidden_channels)
        self.conv_mu = GCNConv(hidden_channels, out_channels)
        self.conv_logstd = GCNConv(hidden_channels, out_channels)
    
    def forward(self, x, edge_index):
        x = F.relu(self.conv1(x, edge_index))
        return self.conv_mu(x, edge_index), self.conv_logstd(x, edge_index)

# Train as VGAE on valid panels
# At inference: high reconstruction loss = potential anomaly
```

---

## Alternative Approaches (For Reference)

### Graph Attention Networks (GAT)

**Reference**: Veličković, P., Cucurull, G., et al. "Graph Attention Networks." ICLR 2018. [arXiv:1710.10903](https://arxiv.org/abs/1710.10903)

GAT may outperform GraphSAGE for feature classification because manufacturing geometry has meaningful local structure (e.g., a shelf pin row context helps classify individual holes). However, it is slightly more complex and less stable at small data scales.

```python
from torch_geometric.nn import GATConv

# Future: compare GAT vs SAGE performance on BENCH-001
# Hypothesis: GAT's attention mechanism better captures spatial context
```

### Graph Isomorphism Network (GIN)

**Reference**: Xu, K., et al. "How Powerful are Graph Neural Networks?" ICLR 2019. [arXiv:1810.00826](https://arxiv.org/abs/1810.00826)

GIN is theoretically more powerful than GraphSAGE at distinguishing graph structures. May be worth benchmarking for manufacturability detection.

### Pre-trained Geometric Models

Future direction: use pre-trained geometric encoders (from ABC Dataset training) as feature initialization before fine-tuning on OMIM tasks.

---

## Self-Supervised Graph Embeddings (Better Than Supervised for v0)

**The honest situation**: With 1,000 synthetic samples, supervised GNN classification (BENCH-001) will likely overfit or underperform. A more appropriate research question for the hackathon scale is:

> *Can we learn useful manufacturing geometry embeddings without labels, using self-supervised contrastive learning on the graph structure alone?*

**Why self-supervised is likely better here:**
- No label dependency — doesn't require perfect synthetic ground truth
- Learns structural patterns (shelf pin rows look similar to each other)
- Can be pre-trained on large unlabeled DXF corpus, then fine-tuned
- More robust to ontology gaps (unknown features still get useful embeddings)

**Recommended approach for v0 (if ML time permits):**

```python
# Self-supervised: Graph Contrastive Learning
# Reference: You, Y., et al. "Graph Contrastive Learning with Augmentations." 
#            NeurIPS 2020. arXiv:2010.13902

# Positive pairs: same panel, different augmentations (rotation, jitter, dropout)
# Negative pairs: different panels
# Loss: NT-Xent contrastive loss

# Augmentations for manufacturing graphs:
def augment_mgg(mgg):
    """Manufacturing-appropriate graph augmentations."""
    aug_type = random.choice([
        "coordinate_jitter",      # Add ±0.5mm noise to positions
        "edge_dropout",           # Drop 10% of ADJACENT_TO edges
        "feature_masking",        # Mask 20% of node features
        "subgraph_sampling",      # Sample connected subgraph
    ])
    # Note: do NOT augment by changing feature SIZES — that would change semantic meaning
```

**Embedding objectives** (what good embeddings should capture):
1. **Feature similarity**: SHELF_PIN_HOLE embeddings should cluster together
2. **Spatial awareness**: Features near the edge should embed differently from center features  
3. **Pattern awareness**: Rows of features should embed similarly to other rows
4. **Anomaly sensitivity**: Geometrically unusual features should have high embedding distance from normals

**Measurement**: After training, visualize with UMAP. If clusters roughly correspond to feature classes without using labels → the embedding is capturing manufacturing geometry structure.

---

## Representation Learning Research Direction

Beyond classification, the MGG enables research into manufacturing representation learning:

### 1. Manufacturing Embedding Space

**Question**: Do similar manufacturing intents cluster in embedding space?

Expected: shelf pin holes of different sizes cluster together; hinge cups form a separate cluster; violations cluster near "anomaly" region.

**Research protocol**:
```python
# Train node embeddings with SAGE
# Extract final embeddings for validation set
# Visualize with UMAP/t-SNE
# Measure cluster purity (NMI, ARI)
```

### 2. Transfer Learning

**Question**: Do GNNs trained on synthetic panel data transfer to real panel DXFs?

This is the key research question for OMIM's long-term impact. If yes: synthetic data generation infrastructure enables training powerful manufacturing models without expensive manual labeling.

**Expected challenge**: Domain gap between procedurally generated and real-world DXFs (noise, non-standard conventions, unusual features).

### 3. Relationship Learning

**Question**: Can GNNs learn manufacturing operation dependencies (DEPENDS_ON edges)?

Important for scheduling and process planning. The BENCH-003 task is a starting point; more complex version would predict full operation DAGs.

---

## ML Constraints (Hard Limits)

| ML CAN | ML CANNOT |
|--------|-----------|
| Classify feature types with confidence | Change geometry measurements |
| Estimate operation likelihood | Override deterministic rule results |
| Score anomalies | Assert new manufacturing rules |
| Rank hypotheses | Claim certainty without evidence |
| Run as optional module | Block pipeline if unavailable |

**Implementation note**: All ML modules should be importable-fail-gracefully:

```python
# omim/semantic/inference_engine.py

try:
    from omim.ml.models.gnn_classifier import ManufacturingFeatureGNN
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("ML dependencies not installed; using heuristics only")

def infer_features(mgg: ManufacturingGeometryGraph) -> list[SemanticAnnotation]:
    if ML_AVAILABLE and model_checkpoint_exists():
        return _ml_inference(mgg)
    else:
        return _heuristic_inference(mgg)  # always available
```

---

## Training Infrastructure Notes

### For 1000 synthetic samples (hackathon scale)
- CPU training is feasible (small graphs, small dataset)
- Training time: ~5-15 minutes for 100 epochs
- Memory: < 2GB RAM

### For 100k+ samples (post-hackathon scale)
- GPU strongly recommended
- Consider DGL for distributed graph learning: https://www.dgl.ai/
- HPC batch job for hyperparameter sweep

### Recommended GPU (if available)
- RTX 3080 or better for small-scale training
- A100 for large-scale experiments
- Google Colab (T4) is sufficient for hackathon baseline

---

## References

| Citation | URL | Relevance |
|---------|-----|-----------|
| Hamilton et al. 2017 (GraphSAGE) | https://arxiv.org/abs/1706.02216 | Primary GNN architecture |
| Veličković et al. 2018 (GAT) | https://arxiv.org/abs/1710.10903 | Alternative architecture |
| Kipf & Welling 2016 (VGAE) | https://arxiv.org/abs/1611.07308 | Anomaly detection approach |
| Xu et al. 2019 (GIN) | https://arxiv.org/abs/1810.00826 | Graph expressiveness theory |
| PyTorch Geometric | https://pytorch-geometric.readthedocs.io/ | Implementation library |
| DGL (Deep Graph Library) | https://www.dgl.ai/ | Alternative GNN library |
| Koch et al. 2019 (ABC Dataset) | https://deep-geometry.github.io/abc-dataset/ | CAD geometry pre-training source |

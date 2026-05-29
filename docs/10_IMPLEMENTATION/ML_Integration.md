# ML Integration

Version: v0.1.0  
Section: 10_IMPLEMENTATION  

See also: [[03_INTERFACES/Semantic_Interface]], [[09_BENCHMARKS/Benchmark_Tasks]], [[01_FOUNDATION/Authority_Hierarchy]]

---

## ML Positioning Statement

**OMIM is not an "AI system."** It is a deterministic manufacturing intelligence infrastructure that includes ML as one optional, bounded layer.

**Do not say:**
- "AI-powered manufacturability analysis"
- "Intelligent manufacturing AI"
- "Smart CNC planning"
- "AI detects manufacturing features"

**Do say:**
- "Rule-based manufacturability validation with ML-assisted semantic annotation"
- "Deterministic validation pipeline with optional GNN feature classification"
- "Manufacturing geometry graph with confidence-annotated feature inference"

This framing matters for scientific credibility, hackathon judges who respect honesty about ML limits, and long-term system trust. **The interesting result is not "the AI works." The interesting result is: "we built infrastructure that makes it possible to measure whether it works."**

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
| Run as optional fallback module | Block the pipeline if unavailable |

**Conflict rule**: If ML output disagrees with a deterministic validation result, the deterministic result is authoritative. Report both. Never silently pick one.

---

## Where ML Fits in the Pipeline

```
DXF → Parser → MGG Builder → Validation Engine → Semantic Layer
                                                       ↑
                                          [ML assists here only]
```

ML operates AFTER validation — it annotates the MGG with semantic hypotheses. It does not validate or modify the underlying geometry.

---

## Graceful Degradation

All ML modules must fail gracefully if dependencies are missing:

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

## ML Task 1: Feature Classification (BENCH-001)

### Model Architecture: GraphSAGE

**Reference**: Hamilton, W.L., Ying, R., Leskovec, J. "Inductive Representation Learning on Large Graphs." NeurIPS 2017. [arXiv:1706.02216](https://arxiv.org/abs/1706.02216)

GraphSAGE is chosen because:
1. **Inductive**: Generalizes to unseen panels at inference (no retraining needed per panel)
2. **Efficient**: Neighbor sampling scales to large graphs
3. **Well-understood**: Stable, reproducible, widely cited baseline
4. **Appropriate for v0**: More advanced architectures (GIN, GPS-Transformer) are premature at 1k samples

```python
# omim/ml/models/gnn_classifier.py

import torch
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv, BatchNorm

class ManufacturingFeatureGNN(torch.nn.Module):
    """
    GraphSAGE-based manufacturing feature classifier.

    Input:  Manufacturing Geometry Graph nodes with geometric features
    Output: Feature class probabilities per node (softmax over 13 classes)

    Reference: Hamilton et al., NeurIPS 2017 (arXiv:1706.02216)
    """

    def __init__(
        self,
        in_channels: int,          # input feature dimensionality (16 per node)
        hidden_channels: int = 128,
        out_channels: int = 13,    # number of feature classes in ontology
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
        for conv, norm in zip(self.convs[:-1], self.norms):
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

Each geometry node is represented as a 16-dimensional feature vector:

```python
# omim/ml/graph_converter.py

def geometry_node_to_features(node: GeometryNode) -> list[float]:
    """
    Convert a GeometryNode to a fixed-size feature vector for GNN input.

    Feature vector (dimension: 16):
    [0]  area_normalized          area / max_area (0–1)
    [1]  perimeter_normalized     perimeter / max_perimeter (0–1)
    [2]  aspect_ratio             bounding_box_width / bounding_box_height (log-scaled)
    [3]  circularity              4π·area / perimeter² (0–1; 1.0 = perfect circle)
    [4]  diameter_normalized      diameter / 100mm (for circles; 0 for non-circles)
    [5]  is_circle                binary: 1.0 if circle entity
    [6]  is_closed                binary: 1.0 if closed contour
    [7]  is_outer_boundary        binary: 1.0 if panel outer boundary
    [8]  centroid_x_normalized    x_centroid / panel_width (0–1)
    [9]  centroid_y_normalized    y_centroid / panel_height (0–1)
    [10] layer_cut                one-hot: CUT layer
    [11] layer_drill              one-hot: DRILL layer
    [12] layer_pocket             one-hot: POCKET layer
    [13] layer_other              one-hot: other layer
    [14] n_contained_features     number of features inside this node (normalized)
    [15] distance_to_edge_norm    distance to nearest panel edge / panel_size (0–1)
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
        ...

    def train(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader,
        checkpoint_dir: str,
    ) -> TrainingResult:
        """
        Training loop with early stopping.

        Loss:      Cross-entropy with class weights (to handle SHELF_PIN_HOLE dominance)
        Optimizer: Adam with weight decay
        Scheduler: ReduceLROnPlateau on val macro F1
        Logging:   loss + macro F1 per epoch
        """
```

### Class Imbalance Handling

In the default feature distribution, SHELF_PIN_HOLE dominates (~40% of all hole features). Use inverse-frequency class weighting:

```python
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

## ML Task 2: Manufacturability Prediction (BENCH-002)

### Research Question

> Can a GNN learn to detect manufacturing violations without explicit rule programming?

The deterministic rule engine IS the ground truth. The ML model is testing whether graph structure encodes enough information to infer violations. If yes: GNNs can learn manufacturing rules from data. If no: validates that rule-based systems are necessary.

### Model Architecture: Graph-Level Binary Classifier

```python
# omim/ml/models/manufacturability_gnn.py

from torch_geometric.nn import global_mean_pool, global_max_pool

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

        # Global mean + max pooling (captures both average and extreme node features)
        x_mean = global_mean_pool(x, batch)
        x_max  = global_max_pool(x, batch)
        x_global = torch.cat([x_mean, x_max], dim=1)

        return self.classifier(x_global).squeeze(-1)
```

---

## ML Task 3: Anomaly Detection (BENCH-004)

### Approach: Variational Graph Autoencoder

**Reference**: Kipf, T.N., Welling, M. "Variational Graph Auto-Encoders." NIPS Workshop 2016. [arXiv:1611.07308](https://arxiv.org/abs/1611.07308)

Train on valid panels only. Anomaly score = reconstruction error for each node. High reconstruction loss at inference → potential anomaly.

```python
# omim/ml/models/vgae_anomaly.py

from torch_geometric.nn import GAE, VGAE, GCNConv

class VariationalManufacturingEncoder(torch.nn.Module):
    def __init__(self, in_channels, hidden_channels, out_channels):
        super().__init__()
        self.conv1    = GCNConv(in_channels, hidden_channels)
        self.conv_mu  = GCNConv(hidden_channels, out_channels)
        self.conv_logstd = GCNConv(hidden_channels, out_channels)

    def forward(self, x, edge_index):
        x = F.relu(self.conv1(x, edge_index))
        return self.conv_mu(x, edge_index), self.conv_logstd(x, edge_index)

# Train with VGAE on valid panels only
# model = VGAE(VariationalManufacturingEncoder(16, 64, 32))
# At inference: high reconstruction loss → anomaly candidate
```

---

## Alternative Architectures (For Reference)

### Graph Attention Networks (GAT)

**Reference**: Veličković, P., et al. "Graph Attention Networks." ICLR 2018. [arXiv:1710.10903](https://arxiv.org/abs/1710.10903)

GAT may outperform GraphSAGE for feature classification because manufacturing geometry has meaningful local structure (e.g., shelf pin row context helps classify individual holes). Slightly more complex and less stable at small data scales.

### Graph Isomorphism Network (GIN)

**Reference**: Xu, K., et al. "How Powerful are Graph Neural Networks?" ICLR 2019. [arXiv:1810.00826](https://arxiv.org/abs/1810.00826)

GIN is theoretically more powerful than GraphSAGE at distinguishing graph structures. May outperform SAGE for manufacturability detection.

---

## Self-Supervised Graph Embeddings (Better Than Supervised for Hackathon Scale)

With 1,000 synthetic samples, supervised GNN classification will likely underperform due to limited data. A more appropriate research question:

> *Can we learn useful manufacturing geometry embeddings without labels, using self-supervised contrastive learning on graph structure alone?*

**Why self-supervised is likely better at 1k samples:**
- No label dependency — doesn't require perfect synthetic ground truth
- Learns structural patterns (shelf pin rows look similar to each other)
- Can be pre-trained on large unlabeled DXF corpus, then fine-tuned on labeled samples
- More robust to ontology gaps (unknown features get useful embeddings)

```python
# Self-supervised: Graph Contrastive Learning
# Reference: You, Y., et al. "Graph Contrastive Learning with Augmentations."
#            NeurIPS 2020. arXiv:2010.13902

# Positive pairs: same panel, different augmentations
# Negative pairs: different panels
# Loss: NT-Xent contrastive loss

def augment_mgg(mgg):
    """Manufacturing-appropriate graph augmentations."""
    aug_type = random.choice([
        "coordinate_jitter",    # Add ±0.5mm noise to positions
        "edge_dropout",         # Drop 10% of ADJACENT_TO edges
        "feature_masking",      # Mask 20% of node features
        "subgraph_sampling",    # Sample connected subgraph
    ])
    # Note: do NOT augment by changing feature SIZES — that changes semantic meaning
```

**Embedding objectives** (what good embeddings should capture):
1. **Feature similarity**: SHELF_PIN_HOLE embeddings cluster together
2. **Spatial awareness**: Edge features embed differently from center features
3. **Pattern awareness**: Rows of features embed similarly to other rows
4. **Anomaly sensitivity**: Geometrically unusual features have high distance from normals

**Measurement**: After training, visualize with UMAP. Clusters that roughly correspond to feature classes (without labels) indicate the embedding captures manufacturing geometry structure.

---

## Research Directions

### Manufacturing Embedding Space

**Question**: Do similar manufacturing intents cluster in embedding space?

```python
# Train node embeddings with GraphSAGE
# Extract final embeddings for validation set
# Visualize with UMAP/t-SNE
# Measure cluster purity (NMI, ARI)
```

Expected: shelf pin holes of different sizes cluster together; hinge cups form a separate cluster; violations cluster near "anomaly" region.

### Transfer Learning

**Question**: Do GNNs trained on synthetic panel data transfer to real panel DXFs?

This is the key research question for OMIM's long-term impact. If yes: synthetic data generation infrastructure enables training powerful manufacturing models without expensive manual labeling. Expected challenge: domain gap (noise, non-standard layer conventions, unusual features in real DXFs).

### Relationship Learning

**Question**: Can GNNs learn manufacturing operation dependencies (DEPENDS_ON edges)?

Important for scheduling and process planning. BENCH-003 is the starting point; more complex version would predict full operation DAGs.

---

## Training Infrastructure Notes

### Hackathon Scale (1,000 samples)
- CPU training is feasible — small graphs, small dataset
- Training time: ~5–15 minutes for 100 epochs
- Memory: < 2GB RAM

### Post-Hackathon Scale (100k+ samples)
- GPU strongly recommended
- DGL for distributed graph learning: https://www.dgl.ai/
- HPC batch job for hyperparameter sweep

### Recommended Hardware
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
| You et al. 2020 (GraphCL) | https://arxiv.org/abs/2010.13902 | Self-supervised contrastive learning |
| PyTorch Geometric | https://pytorch-geometric.readthedocs.io/ | Implementation library |
| DGL (Deep Graph Library) | https://www.dgl.ai/ | Alternative GNN library |
| Koch et al. 2019 (ABC Dataset) | https://deep-geometry.github.io/abc-dataset/ | CAD geometry pre-training source |

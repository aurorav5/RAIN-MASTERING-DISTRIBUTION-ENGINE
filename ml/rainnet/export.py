"""Export RainNet v2 to ONNX. Exports untrained model for integration testing."""
import argparse
import torch
import torch.onnx
from pathlib import Path


def export_onnx(checkpoint_path: str = "", output_path: str = "../../models/rain_base.onnx") -> str:
    from ml.rainnet.model import RainNetV2  # type: ignore[import]

    model = RainNetV2()
    if checkpoint_path:
        state = torch.load(checkpoint_path, map_location="cpu")
        model.load_state_dict(state["model_state_dict"])
    model.eval()

    dummy_mel = torch.randn(1, 1, 128, 128)
    dummy_artist = torch.zeros(1, 64)
    dummy_genre = torch.zeros(1, dtype=torch.long)
    dummy_platform = torch.zeros(1, dtype=torch.long)
    dummy_mode = torch.ones(1, 1)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    torch.onnx.export(
        model,
        (dummy_mel, dummy_artist, dummy_genre, dummy_platform, dummy_mode),
        output_path,
        input_names=["mel", "artist_vec", "genre_id", "platform_id", "simple_mode"],
        output_names=["params_raw"],
        dynamic_axes={
            "mel":          {0: "batch"},
            "artist_vec":   {0: "batch"},
            "genre_id":     {0: "batch"},
            "platform_id":  {0: "batch"},
            "simple_mode":  {0: "batch"},
            "params_raw":   {0: "batch"},
        },
        opset_version=17,
        do_constant_folding=True,
    )
    print(f"Exported RainNet v2 to {output_path}")

    import onnx
    import onnxruntime as ort

    onnx_model = onnx.load(output_path)
    onnx.checker.check_model(onnx_model)

    sess = ort.InferenceSession(output_path, providers=["CPUExecutionProvider"])
    out = sess.run(None, {
        "mel":          dummy_mel.numpy(),
        "artist_vec":   dummy_artist.numpy(),
        "genre_id":     dummy_genre.numpy(),
        "platform_id":  dummy_platform.numpy(),
        "simple_mode":  dummy_mode.numpy(),
    })
    assert out[0].shape == (1, 46), f"Unexpected output shape: {out[0].shape}"
    print(f"ONNX validation OK. Output shape: {out[0].shape}")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", default="")
    parser.add_argument("--output", default="../../models/rain_base.onnx")
    args = parser.parse_args()
    export_onnx(args.checkpoint, args.output)

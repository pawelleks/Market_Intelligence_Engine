# Fix for potential Deadlocks on Mac M1/M2: Import TensorFlow BEFORE everything else
import os
# Disable OneDNN optimization if not already disabled
os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS', '0')

import tensorflow as tf
import numpy as np
import pandas as pd
import json
import base64
import io
from pathlib import Path
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split

# Local Imports
from mie_lib.analytics.gaf.dataset import fetch_and_prepare_data, create_windows_and_labels
from mie_lib.analytics.gaf.encoder import GAFEncoder
from mie_lib.analytics.gaf.model import train_model

MODEL_PATH = Path("data/models/gaf_cnn.h5")
LATEST_JSON = Path("data/analytics/gaf/latest.json")

def run_training_pipeline(ticker="SPY", window_size=20, epochs=20):
    """Fetches data, creates GAF dataset, trains CNN, saves model."""
    print(f"Fetching data for {ticker}...")
    df = fetch_and_prepare_data(ticker)
    
    print("Creating GAF Dataset...")
    # NOTE: create_windows_and_labels needs to return Volume too!
    # Ideally we should refactor that, but let's do it inline here for safety/speed 
    # since we are modifying the pipeline logic heavily.
    
    # 1. Prepare Data Arrays
    prices = df['adj_close' if 'adj_close' in df.columns else 'close'].values
    volumes = df['volume'].values
    dates = df['date'].values
    
    # 2. Creates Labels
    # Target: 1 if Next Close > Current Close
    targets = (prices[1:] > prices[:-1]).astype(int)
    # Align arrays: prices[:-1] aligns with targets. 
    # But we need windows ending at index `i`.
    
    X_prices = []
    X_volumes = []
    y = []
    valid_dates = []
    
    # Range: start at window_size, end at len(prices)-1 (since targets needs t+1)
    for i in range(window_size, len(prices) - 1):
        X_prices.append(prices[i-window_size : i])
        X_volumes.append(volumes[i-window_size : i])
        y.append(targets[i-1]) # Target for prediction made at 'i-1' (conceptually, i is the day we make decision)
        # Wait, simple logic:
        # At day `i`, we have history `i-W : i`. We predict move `i -> i+1`.
        # So we check `prices[i+1] > prices[i]`.
        
        y_val = 1 if prices[i+1] > prices[i] else 0
        y.append(y_val)
        valid_dates.append(dates[i])
        
    # Re-slice properly because I doubled appended y above by mistake in thought
    X_prices = []
    X_volumes = []
    y = []
    
    for i in range(window_size, len(prices)-1):
        X_prices.append(prices[i-window_size : i + 1][-window_size:]) # Ensure exact width
        X_volumes.append(volumes[i-window_size : i + 1][-window_size:])
        
        # Target: Return of (i+1) vs (i)
        is_up = prices[i+1] > prices[i]
        y.append(1 if is_up else 0)
        
    X_prices = np.array(X_prices)
    X_volumes = np.array(X_volumes)
    y = np.array(y)
    
    # Check if we have enough data
    if len(y) < 100:
        print("Not enough data to train.")
        return

    # Encode GAF
    print("Encoding Dual-Channel GAF images...")
    encoder = GAFEncoder(image_size=window_size)
    X_gaf = encoder.encode_batch(X_prices, X_volumes) # (N, 40, 40, 2)
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(X_gaf, y, test_size=0.2, shuffle=False)
    
    print(f"Training Model on {len(X_train)} samples...")
    model, history = train_model(X_train, y_train, X_test, y_test, epochs=epochs)
    
    # Save
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save(MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")
    
    # Evaluate
    loss, acc = model.evaluate(X_test, y_test)
    print(f"Test Accuracy: {acc:.2f}")


def make_gradcam_heatmap(model, img_array, last_conv_layer_name, pred_index=None):
    """
    Generates a Grad-CAM heatmap using Model Splitting (Robust for Sequential).
    img_array: (1, 40, 40, 2)
    """
    # 1. Find the index of the target layer
    layer_index = None
    for i, layer in enumerate(model.layers):
        if layer.name == last_conv_layer_name:
            layer_index = i
            break
            
    if layer_index is None:
        raise ValueError(f"Layer {last_conv_layer_name} not found in model.")

    # 2. Split into two sub-models
    try:
        # Use simple gradient tape manual feed
        with tf.GradientTape() as tape:
            # Part 1: Pass through layers up to conv layer
            x = img_array
            for layer in model.layers[:layer_index+1]:
                x = layer(x)
            last_conv_layer_output = x
            
            tape.watch(last_conv_layer_output)
            
            # Part 2: Pass through remaining layers
            for layer in model.layers[layer_index+1:]:
                x = layer(x)
            preds = x
            
            if pred_index is None:
                pred_index = tf.argmax(preds[0])
            class_channel = preds[:, pred_index]

    except Exception as e:
        print(f"Grad-CAM error: {e}")
        return np.zeros((img_array.shape[1], img_array.shape[2]))

    # 3. Compute Gradients
    grads = tape.gradient(class_channel, last_conv_layer_output)
    pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))
    
    heatmap = last_conv_layer_output[0] @ pooled_grads[..., tf.newaxis]
    heatmap = tf.squeeze(heatmap)
    heatmap = tf.maximum(heatmap, 0) / (tf.math.reduce_max(heatmap) + 1e-9)
    return heatmap.numpy()

def run_inference_latest(ticker="SPY", window_size=20):
    """Runs inference on the LATEST window relative to TODAY (predicting tomorrow)."""
    if not MODEL_PATH.exists():
        print("Model not found. Please run train-gaf first.")
        return

    model = tf.keras.models.load_model(MODEL_PATH)
    
    # Ensure correct input shape
    model.build((None, window_size, window_size, 2))

    last_conv_layer_name = None
    for layer in reversed(model.layers):
        if isinstance(layer, tf.keras.layers.Conv2D):
            last_conv_layer_name = layer.name
            break
            
    # Fetch Data
    df = fetch_and_prepare_data(ticker)
    
    if len(df) < window_size:
        print("Not enough recent data.")
        return

    # Get latest WINDOW
    price_col = 'adj_close' if 'adj_close' in df.columns else 'close'
    latest_prices = df[price_col].values[-window_size:]
    latest_volumes = df['volume'].values[-window_size:]
    
    # Encode Dual Channel
    encoder = GAFEncoder(image_size=window_size)
    gaf_img = encoder.encode_window(latest_prices, latest_volumes) # (40, 40, 2)
    
    # Predict
    # Add batch dim: (1, 40, 40, 2)
    input_tensor = gaf_img[np.newaxis, ...]
    prob = model.predict(input_tensor)[0][0] # Sigmoid output
    
    prediction = "UP" if prob > 0.5 else "DOWN"
    confidence = prob if prob > 0.5 else (1 - prob)
    
    # --- Grad-CAM Generation ---
    gradcam_base64 = None
    if last_conv_layer_name:
        try:
            # Generate heatmap (H, W)
            heatmap = make_gradcam_heatmap(model, input_tensor, last_conv_layer_name)
            
            # Matplotlib Overlay
            # Use CHANNEL 0 (Price) for the background image
            price_channel_img = gaf_img[:, :, 0]
            
            buf_cam = io.BytesIO()
            plt.figure(figsize=(3, 3))
            
            # Plot 1: Original Image (Price Channel)
            plt.imshow(price_channel_img, cmap='rainbow', origin='lower', alpha=1.0)
            
            # Plot 2: Heatmap Overlay
            plt.imshow(heatmap, cmap='jet', alpha=0.5, origin='lower', extent=[0, window_size-1, 0, window_size-1])
            
            plt.axis('off')
            plt.savefig(buf_cam, format='png', bbox_inches='tight', pad_inches=0)
            plt.close()
            gradcam_base64 = base64.b64encode(buf_cam.getvalue()).decode('utf-8')
            
        except Exception as e:
            print(f"Grad-CAM generation failed: {e}")
    else:
        print("No Conv2D layer found for Grad-CAM.")

    # Create Base64 Image for Frontend (Price Channel Only)
    price_channel_img = gaf_img[:, :, 0]
    buf = io.BytesIO()
    plt.figure(figsize=(3, 3))
    plt.imshow(price_channel_img, cmap='rainbow', origin='lower')
    plt.axis('off')
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0)
    plt.close()
    img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    
    # --- Prepare OHLC & Attention Data for Chart ---
    window_df = df.iloc[-window_size:].copy()
    ohlc_data = []
    
    # 1D Attention Score (Sum of columns)
    attention_scores = []
    if 'heatmap' in locals():
        col_sums = np.sum(heatmap, axis=0)
        norm_sums = (col_sums - col_sums.min()) / (col_sums.max() - col_sums.min() + 1e-9)
        attention_scores = norm_sums.tolist()
    else:
        attention_scores = [0.0] * window_size

    for i in range(len(window_df)):
        row = window_df.iloc[i]
        dt_str = str(row['date'].date()) if 'date' in row else str(df['date'].iloc[-window_size+i].date())
        
        o = row.get('open', row.get('Open', 0))
        h = row.get('high', row.get('High', 0))
        l = row.get('low', row.get('Low', 0))
        c = row.get('adj_close', row.get('close', row.get('Close', 0))) # Prefer adj_close
        v = row.get('volume', row.get('Volume', 0))
        
        score = attention_scores[i] if i < len(attention_scores) else 0.0
        
        ohlc_data.append({
            "time": dt_str,
            "open": float(o),
            "high": float(h),
            "low": float(l),
            "close": float(c),
            "volume": float(v),
            "attention": float(score)
        })

    result = {
        "ticker": ticker,
        "date": str(df['date'].iloc[-1].date()), # Latest data date
        "prediction": prediction,
        "probability": float(confidence),
        "raw_score": float(prob),
        "image_base64": f"data:image/png;base64,{img_base64}",
        "gradcam_image_base64": gradcam_base64,
        "ohlc_data": ohlc_data
    }
    
    LATEST_JSON.parent.mkdir(parents=True, exist_ok=True)
    with LATEST_JSON.open('w') as f:
        json.dump(result, f, indent=2)
        
    print(f"Prediction: {prediction} ({confidence:.1%}) -> Saved to {LATEST_JSON}")

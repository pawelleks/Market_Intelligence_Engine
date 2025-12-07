import tensorflow as tf
from tensorflow.keras import layers, models, optimizers

def create_gaf_cnn_model(input_shape=(20, 20, 1)):
    """
    Creates a simple CNN for binary classification of GAF images.
    """
    model = models.Sequential([
        # Standard GAF images are small (e.g. 20x20), so filter sizes and pooling must be careful.
        layers.Input(shape=input_shape),
        
        # Conv Block 1
        layers.Conv2D(32, (3, 3), activation='relu', padding='same'),
        layers.MaxPooling2D((2, 2)),
        
        # Conv Block 2
        layers.Conv2D(64, (3, 3), activation='relu', padding='same'),
        layers.MaxPooling2D((2, 2)),
        
        # Classifier
        layers.Flatten(),
        layers.Dense(64, activation='relu'),
        layers.Dropout(0.5), # prevent overfitting
        layers.Dense(1, activation='sigmoid') # Binary: UP (1) or DOWN (0)
    ])
    
    model.compile(optimizer='adam',
                  loss='binary_crossentropy',
                  metrics=['accuracy'])
    return model

def train_model(X_train, y_train, X_val, y_val, epochs=50, batch_size=32):
    """
    Train the GAF CNN model.
    """
    # GAF outputs (N, H, W), we need (N, H, W, 1) for Conv2D channel dim
    if len(X_train.shape) == 3:
        X_train = X_train[..., tf.newaxis]
        X_val = X_val[..., tf.newaxis]
        
    model = create_gaf_cnn_model(input_shape=X_train.shape[1:])
    
    history = model.fit(
        X_train, y_train,
        epochs=epochs,
        batch_size=batch_size,
        validation_data=(X_val, y_val),
        verbose=1
    )
    return model, history

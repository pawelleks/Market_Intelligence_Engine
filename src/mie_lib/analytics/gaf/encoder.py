import numpy as np
from pyts.image import GramianAngularField
from typing import Tuple

class GAFEncoder:
    def __init__(self, image_size: int = 20, method: str = 'summation'):
        """
        Initialize GAF Encoder.
        :param image_size: Output dimension of the GAF image (image_size x image_size). 
                           Also determines the window size if raw data matches.
        :param method: 'summation' or 'difference'
        """
        self.image_size = image_size
        self.gadf = GramianAngularField(image_size=image_size, method=method)

    def encode_window(self, window_data: np.ndarray, volume_data: np.ndarray = None) -> np.ndarray:
        """
        Encode a single window of price data (and optional volume) into a GAF image.
        :param window_data: 1D array of prices
        :param volume_data: 1D array of volumes (optional)
        :return: 3D array (image_size, image_size, channels) 
                 Channels = 1 if no volume, 2 if volume provided.
        """
        # 1. Price Channel
        X_price = window_data.reshape(1, -1)
        gaf_price = self.gadf.transform(X_price)[0] # (N, N)
        
        if volume_data is None:
            # Single Channel (Legacy)
            return gaf_price
            
        # 2. Volume Channel
        # Normalize volume explicitly before GAF? 
        # GAF uses min-max scaling internally (-1 to 1) usually.
        X_vol = volume_data.reshape(1, -1)
        gaf_vol = self.gadf.transform(X_vol)[0] # (N, N)
        
        # Stack channels: (N, N) -> (N, N, 2)
        return np.dstack((gaf_price, gaf_vol))

    def encode_batch(self, batch_prices: np.ndarray, batch_volumes: np.ndarray = None) -> np.ndarray:
        """
        Encode a batch of windows.
        :param batch_prices: (n_samples, window_size)
        :param batch_volumes: (n_samples, window_size)
        :return: (n_samples, image_size, image_size, channels)
        """
        # Price GAFs -> (n_samples, image_size, image_size)
        gaf_prices = self.gadf.transform(batch_prices)
        
        if batch_volumes is None:
            return gaf_prices
            
        # Volume GAFs
        gaf_vols = self.gadf.transform(batch_volumes)
        
        # Stack along last axis (create channel dim)
        # We need to add a channel dim to each first if they are (N, H, W)
        # Result should be (N, H, W, 2)
        return np.stack((gaf_prices, gaf_vols), axis=-1)

import os
import sys
import re
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
from rasterio.mask import mask
import geopandas as gpd
import math
from PyQt5.QtWidgets import QMessageBox, QInputDialog

def read_mtl(caminho_mtl):
    """
    Lê o arquivo MTL e extrai os metadados necessários.
    """
    mtl_data = {}
    try:
        with open(caminho_mtl, 'r') as file:
            for line in file:
                parts = line.strip().split('=')
                if len(parts) == 2:
                    key, value = parts
                    mtl_data[key.strip()] = value.strip().strip('"')
    except IOError:
        print("Erro ao ler o arquivo MTL. Verifique o caminho fornecido.")
        sys.exit(1)
    return mtl_data

def recortar_e_aliar_mdt(caminho_mdt, shapefile_path, output_path, caminho_raster_referencia):
    """
    Recorta e alinha o MDT (Modelo Digital de Terreno) de acordo com o shapefile fornecido.
    """
    try:
        with rasterio.open(caminho_raster_referencia) as ref_raster:
            ref_transform = ref_raster.transform
            ref_crs = ref_raster.crs
            ref_width = ref_raster.width
            ref_height = ref_raster.height

        with rasterio.open(caminho_mdt) as src:
            shapefile = gpd.read_file(shapefile_path)
            if shapefile.empty:
                print("Erro: Shapefile vazio ou não intersecta o MDT.")
                return None, None
            geometrias = [feature["geometry"] for feature in shapefile.__geo_interface__['features']]
            out_image, out_transform = mask(src, geometrias, crop=True)
            if out_image.size == 0:
                print("Erro: A máscara resultou em uma imagem vazia.")
                return None, None
            out_meta = src.meta.copy()
            out_meta.update({
                "driver": "GTiff",
                "height": ref_height,
                "width": ref_width,
                "transform": ref_transform,
                "crs": ref_crs,
                "nodata": src.nodata
            })
            reamostrado_image = np.zeros((ref_height, ref_width), dtype=src.dtypes[0])
            reproject(
                source=out_image,
                destination=reamostrado_image,
                src_transform=out_transform,
                src_crs=src.crs,
                dst_transform=ref_transform,
                dst_crs=ref_crs,
                resampling=Resampling.nearest
            )
            with rasterio.open(output_path, 'w', **out_meta) as dst:
                dst.write(reamostrado_image, 1)
            return reamostrado_image, out_meta
    except Exception as e:
        print(f"Erro ao recortar e alinhar MDT: {e}")
        return None, None

def process_images(caminho_bandas, shapefile_path, output_dir, mtl_data):
    """
    Processa as imagens das bandas, aplicando o recorte e calculando a reflectância TOA (Top of Atmosphere).
    """
    bandas = {}
    meta_data = None
    if not os.path.exists(caminho_bandas):
        print("Diretório das bandas não encontrado.")
        return None, None, None

    arquivos = [os.path.join(caminho_bandas, arquivo) for arquivo in os.listdir(caminho_bandas) if arquivo.endswith(('.TIF', '.tif'))]
    out_meta = None  # Inicialização de out_meta

    for arquivo in arquivos:
        nome_banda = os.path.basename(arquivo)
        match = re.search(r'_B(\d+)', nome_banda)
        if match:
            band_number = int(match.group(1))
        else:
            print(f"Nenhum número de banda encontrado em {nome_banda}. Pulando este arquivo.")
            continue

        nome_saida = f'band{band_number}.tif'
        try:
            with rasterio.open(arquivo) as src:
                shapefile = gpd.read_file(shapefile_path)
                geometrias = [feature["geometry"] for feature in shapefile.__geo_interface__['features']]
                out_image, out_transform = mask(src, geometrias, crop=True)
                out_meta = src.meta.copy()
                out_meta.update({
                    "driver": "GTiff",
                    "height": out_image.shape[1],
                    "width": out_image.shape[2],
                    "transform": out_transform
                })

                if out_image.ndim == 4:
                    out_image = out_image.reshape((1, *out_image.shape[-2:]))

                if band_number == 10:
                    processed_data = out_image[0]
                else:
                    # Calcula a reflectância TOA
                    reflectance_mult_key = f'REFLECTANCE_MULT_BAND_{band_number}'
                    reflectance_add_key = f'REFLECTANCE_ADD_BAND_{band_number}'
                    sun_elevation = float(mtl_data['SUN_ELEVATION'])
                    if reflectance_mult_key in mtl_data and reflectance_add_key in mtl_data:
                        reflectance_mult = float(mtl_data[reflectance_mult_key])
                        reflectance_add = float(mtl_data[reflectance_add_key])
                        toa_reflectance = (reflectance_mult * out_image[0] + reflectance_add) / np.sin(np.deg2rad(sun_elevation))
                        processed_data = toa_reflectance
                    else:
                        print(f"Chaves de metadados faltando para a banda {band_number}.")
                        continue

                output_path = os.path.join(output_dir, nome_saida)
                with rasterio.open(output_path, 'w', **out_meta) as dst:
                    dst.write(processed_data, 1)
                bandas[nome_saida.replace('.tif', '')] = processed_data

        except Exception as e:
            print(f"Erro ao processar a banda {band_number}: {e}. Pulando.")
            continue

    return bandas, meta_data, out_meta

def run_processing(caminho_mtl, caminho_mdt, caminho_bandas, shapefile_path, output_dir, raster_referencia_path, u_2m, EToi, ETo, gui_dialog):
    """
    Função principal que executa todo o processamento dos dados para calcular a evapotranspiração.
    """
    # Leia os dados do MTL
    mtl_data = read_mtl(caminho_mtl)

    if not mtl_data:
        print("Falha ao carregar dados MTL, terminando o programa.")
        return

    # Recortar e alinhar o MDT
    mdt_output_path = os.path.join(output_dir, 'MDT_Sebal_recorte.tif')
    mdt_recortado, mdt_meta = recortar_e_aliar_mdt(caminho_mdt, shapefile_path, mdt_output_path, raster_referencia_path)

    if mdt_recortado is None:
        print("Falha ao processar MDT.")
        return

    print("Processamento do MDT concluído com sucesso.")

    # Processar as imagens de bandas
    bandas, meta_data, out_meta = process_images(caminho_bandas, shapefile_path, output_dir, mtl_data)

    if not bandas:
        print("Nenhuma banda processada.")
        return

    # Acessar bandas específicas
    nir_band = bandas.get('band5')  # Banda NIR
    red_band = bandas.get('band4')  # Banda Vermelha
    green_band = bandas.get('band3') # Banda Verde
    blue_band = bandas.get('band2')  # Banda Azul
    band1 = bandas.get('band1')
    band2 = bandas.get('band2')
    band3 = bandas.get('band3')
    band4 = bandas.get('band4')
    band5 = bandas.get('band5')
    band6 = bandas.get('band6')
    band7 = bandas.get('band7')
    band10 = bandas.get('band10')

    if nir_band is None or red_band is None or green_band is None or blue_band is None:
        print("Algumas bandas necessárias estão faltando.")
        return

    # Criar composto RGB
    rgb_composite = np.stack((red_band, green_band, blue_band), axis=0)
    rgb_output_path = os.path.join(output_dir, 'CC_432.tif')
    rgb_meta = out_meta.copy()
    rgb_meta.update({
        'driver': 'GTiff',
        'count': 3,
        'dtype': rgb_composite.dtype,
        'width': rgb_composite.shape[2],
        'height': rgb_composite.shape[1]
    })

    try:
        with rasterio.open(rgb_output_path, 'w', **rgb_meta) as dst:
            for i, band in enumerate(rgb_composite, start=1):
                dst.write(band, i)
        print("Composite RGB Landsat 8, be patient... Done!")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    # Calcular NDVI
    NDVI = (nir_band - red_band) / (nir_band + red_band + 1e-10)
    NDVI = np.clip(NDVI, -1, 1)

    ndvi_output_path = os.path.join(output_dir, 'NDVI.tif')
    ndvi_meta = out_meta.copy()
    ndvi_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': 'float32',
        'width': NDVI.shape[1],
        'height': NDVI.shape[0]
    })

    try:
        with rasterio.open(ndvi_output_path, 'w', **ndvi_meta) as dst:
            dst.write(NDVI.astype('float32'), 1)
        print("NDVI salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    # Calcular SAVI
    Lsavi = 0.5
    SAVI = ((nir_band - red_band) / (nir_band + red_band + Lsavi)) * (1 + Lsavi)
    SAVI = np.clip(SAVI, -1, 1)

    savi_output_path = os.path.join(output_dir, 'SAVI.tif')
    savi_meta = out_meta.copy()
    savi_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': 'float32',
        'width': SAVI.shape[1],
        'height': SAVI.shape[0]
    })

    try:
        with rasterio.open(savi_output_path, 'w', **savi_meta) as dst:
            dst.write(SAVI.astype('float32'), 1)
        print("SAVI salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    # Calcular LAI
    def calculate_lai(savi):
        lai = np.zeros_like(savi, dtype=float)
        lai[savi < 0.1] = 0.00001
        mask = (savi >= 0.1) & (savi < 0.687)
        lai[mask] = -np.log((0.69 - savi[mask]) / 0.59) / 0.91
        lai[savi >= 0.687] = 6
        return lai

    LAI = calculate_lai(SAVI)

    lai_output_path = os.path.join(output_dir, 'LAI.tif')
    lai_meta = out_meta.copy()
    lai_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': 'float32',
        'width': LAI.shape[1],
        'height': LAI.shape[0]
    })

    try:
        with rasterio.open(lai_output_path, 'w', **lai_meta) as dst:
            dst.write(LAI.astype('float32'), 1)
        print("LAI salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    # Processar Temperatura de Superfície (Ts)
    radiance_mult_key = 'RADIANCE_MULT_BAND_10'
    radiance_add_key = 'RADIANCE_ADD_BAND_10'
    K1 = float(mtl_data['K1_CONSTANT_BAND_10'])
    K2 = float(mtl_data['K2_CONSTANT_BAND_10'])

    radiance_mult = float(mtl_data[radiance_mult_key])
    radiance_add = float(mtl_data[radiance_add_key])

    radiance = radiance_mult * band10 + radiance_add

    temperature_brightness = K2 / np.log((K1 / radiance) + 1)

    # Cálculo da Emissividade de Banda Estreita (eNBf)
    eNB = np.where((LAI < 3) & (NDVI > 0), 0.97 + 0.0033 * LAI,
                   np.where((LAI >= 3) & (NDVI > 0), 0.98, np.nan))
    eNBf = np.where(np.isnan(eNB), 0.99, eNB)

    eNBf_output_path = os.path.join(output_dir, 'eNBf.tif')
    eNBf_meta = out_meta.copy()
    eNBf_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': eNBf.dtype,
        'width': eNBf.shape[1],
        'height': eNBf.shape[0]
    })

    try:
        with rasterio.open(eNBf_output_path, 'w', **eNBf_meta) as dst:
            dst.write(eNBf, 1)
        print("eNBf salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    # Cálculo da Emissividade de Banda Larga (e0f)
    e0 = np.where((LAI < 3) & (NDVI > 0), 0.95 + 0.01 * LAI,
                  np.where((LAI >= 3) & (NDVI > 0), 0.98, np.nan))
    e0f = np.where(np.isnan(e0), 0.985, e0)

    e0f_output_path = os.path.join(output_dir, 'e0f.tif')
    e0f_meta = out_meta.copy()
    e0f_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': e0f.dtype,
        'width': e0f.shape[1],
        'height': e0f.shape[0]
    })

    try:
        with rasterio.open(e0f_output_path, 'w', **e0f_meta) as dst:
            dst.write(e0f, 1)
        print("e0f salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    Ts = temperature_brightness / (1 + ((10.8 * temperature_brightness / 14380) * np.log(eNBf)))

    Ts_output_path = os.path.join(output_dir, 'Ts.tif')

    Ts_meta = out_meta.copy()
    Ts_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': 'float32',
        'width': Ts.shape[1],
        'height': Ts.shape[0]
    })

    try:
        with rasterio.open(Ts_output_path, 'w', **Ts_meta) as dst:
            dst.write(Ts.astype('float32'), 1)
        print("Ts salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    print("Média da Temperatura de Brilho:", np.mean(temperature_brightness))
    print("Média da Emissividade (Banda Estreita):", np.mean(eNBf))
    print("Média da Emissividade (Banda Larga):", np.mean(e0f))
    print("Média da Temperatura de Superfície:", np.mean(Ts))

    # Cálculo de aTOA e aS
    if 'EARTH_SUN_DISTANCE' in mtl_data:
        d = float(mtl_data['EARTH_SUN_DISTANCE'])
    else:
        print("Chave 'EARTH_SUN_DISTANCE' não encontrada no MTL.")
        return

    radiance_maximum = {}
    reflectance_maximum = {}

    for key, value in mtl_data.items():
        if 'RADIANCE_MAXIMUM_BAND_' in key:
            radiance_maximum[key] = float(value)
        elif 'REFLECTANCE_MAXIMUM_BAND_' in key:
            reflectance_maximum[key] = float(value)

    ESUN = []
    for i in range(1, 8):
        rad_max_key = f'RADIANCE_MAXIMUM_BAND_{i}'
        ref_max_key = f'REFLECTANCE_MAXIMUM_BAND_{i}'
        if rad_max_key in radiance_maximum and ref_max_key in reflectance_maximum:
            ESUN_i = (math.pi * d * d) * (radiance_maximum[rad_max_key] / reflectance_maximum[ref_max_key])
            ESUN.append(ESUN_i)
        else:
            print(f"Chaves de radiância ou reflectância máxima faltando para a banda {i}.")
            ESUN.append(0)

    W = [value / sum(ESUN) for value in ESUN]

    W1, W2, W3, W4, W5, W6, W7 = W

    aTOA = (band1 * W1 + band2 * W2 + band3 * W3 + band4 * W4 + band5 * W5 + band6 * W6 + band7 * W7)

    aTOA_output_path = os.path.join(output_dir, 'aTOA.tif')
    aTOA_meta = out_meta.copy()
    aTOA_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': aTOA.dtype,
        'width': aTOA.shape[1],
        'height': aTOA.shape[0]
    })

    try:
        with rasterio.open(aTOA_output_path, 'w', **aTOA_meta) as dst:
            dst.write(aTOA, 1)
        print("aTOA salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    # Cálculo de Tsw
    Tsw = 0.75 + 0.00002 * mdt_recortado

    Tsw_output_path = os.path.join(output_dir, 'Tsw.tif')

    Tsw_meta = out_meta.copy()
    Tsw_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': Tsw.dtype,
        'width': Tsw.shape[1],
        'height': Tsw.shape[0]
    })

    try:
        with rasterio.open(Tsw_output_path, 'w', **Tsw_meta) as dst:
            dst.write(Tsw, 1)
        print("Tsw salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    # Calculando o albedo da superfície (aS)
    aS = (aTOA - 0.03) / (Tsw ** 2)

    aS_output_path = os.path.join(output_dir, 'aS.tif')

    aS_meta = out_meta.copy()
    aS_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': aS.dtype,
        'width': aS.shape[1],
        'height': aS.shape[0]
    })

    try:
        with rasterio.open(aS_output_path, 'w', **aS_meta) as dst:
            dst.write(aS, 1)
        print("aS salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    # Calcular Rsi
    sun_elevation = float(mtl_data['SUN_ELEVATION'])
    SUN_ELEVATION_rad = np.deg2rad(90 - sun_elevation)
    Rsi = 1367 * np.cos(SUN_ELEVATION_rad) * (1 / (d**2)) * Tsw

    Rsi_output_path = os.path.join(output_dir, 'Rsi.tif')

    Rsi_meta = out_meta.copy()
    Rsi_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': 'float32',
        'width': Rsi.shape[1],
        'height': Rsi.shape[0]
    })

    try:
        with rasterio.open(Rsi_output_path, 'w', **Rsi_meta) as dst:
            dst.write(Rsi.astype('float32'), 1)
        print("Rsi salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    # Calcular RLo
    RLo = e0f * 5.67e-8 * (Ts ** 4)

    RLo_output_path = os.path.join(output_dir, 'RLo.tif')

    RLo_meta = out_meta.copy()
    RLo_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': 'float32',
        'width': RLo.shape[1],
        'height': RLo.shape[0]
    })

    try:
        with rasterio.open(RLo_output_path, 'w', **RLo_meta) as dst:
            dst.write(RLo.astype('float32'), 1)
        print("RLo salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    # Criação da Máscara do Pixel Frio (Pcold)
    Ts_median = np.nanmedian(Ts)
    Pcold = np.where((NDVI > 0.4) & (Ts < Ts_median), Ts, np.nan)

    Pcold_output_path = os.path.join(output_dir, 'Pcold.tif')

    Pcold_meta = out_meta.copy()
    Pcold_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': 'float32',
        'width': Pcold.shape[1],
        'height': Pcold.shape[0]
    })

    try:
        with rasterio.open(Pcold_output_path, 'w', **Pcold_meta) as dst:
            dst.write(Pcold.astype('float32'), 1)
        print("Pcold salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    # Solicitar as coordenadas de PCold
    try:
        ts_file_path = os.path.join(output_dir, 'Ts.tif')
        tsw_file_path = os.path.join(output_dir, 'Tsw.tif')

        with rasterio.open(ts_file_path) as ts_src, rasterio.open(tsw_file_path) as tsw_src:
            # Solicitar as coordenadas de PCold
            pcold_coords_str, ok = QInputDialog.getText(gui_dialog, 'Coordenadas PCold', 'Insira as coordenadas do PCold (easting, northing):')
            if not ok:
                QMessageBox.warning(gui_dialog, "Processamento Cancelado", "Processamento cancelado pelo usuário.")
                return
            row_pcold, col_pcold = ts_src.index(*map(float, pcold_coords_str.strip().split(',')))
            z_TsPcold = ts_src.read(1)[row_pcold, col_pcold]
            Tsw_value = tsw_src.read(1)[row_pcold, col_pcold]

            print("Cold pixel temperature:", z_TsPcold, "K")
            print("Tsw value at cold pixel:", Tsw_value)

            RLi = 0.85 * ((-np.log(Tsw_value)) ** 0.09) * 5.67e-8 * z_TsPcold ** 4
            print("Calculating incoming longwave radiation (RLi) - W/m2... Done!")

            RLi_output_path = os.path.join(output_dir, 'RLi.tif')

            RLi_array = np.full(ts_src.shape, RLi, dtype='float32')

            RLi_meta = ts_src.meta.copy()
            RLi_meta.update({
                'dtype': 'float32',
                'count': 1
            })

            with rasterio.open(RLi_output_path, 'w', **RLi_meta) as dst:
                dst.write(RLi_array, 1)
            print("RLi salvo com sucesso.")

    except Exception as e:
        print(f"Erro ao processar PCold: {e}")
        return

    # Calcular Rn
    rsi_file_path = os.path.join(output_dir, 'Rsi.tif')
    as_file_path = os.path.join(output_dir, 'aS.tif')

    try:
        with rasterio.open(rsi_file_path) as src_rsi:
            Rsi = src_rsi.read(1)
        with rasterio.open(as_file_path) as src_as:
            aS = src_as.read(1)

        Rn = (1 - aS) * Rsi + RLi - RLo - (1 - e0f) * RLi

        Rn_output_path = os.path.join(output_dir, 'Rn.tif')

        Rn_meta = src_rsi.meta.copy()
        Rn_meta.update({
            'driver': 'GTiff',
            'count': 1,
            'dtype': 'float32',
            'width': Rn.shape[1],
            'height': Rn.shape[0]
        })

        with rasterio.open(Rn_output_path, 'w', **Rn_meta) as dst:
            dst.write(Rn.astype('float32'), 1)
        print("Rn salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao processar ou salvar os rasters: {e}")

    # Calcular G
    G_Rn = np.where(NDVI < 0, 0.5, ((Ts - 273.15) / aS) * (0.0038 * aS + 0.0074 * aS ** 2) * (1 - 0.98 * NDVI ** 4))
    G = G_Rn * Rn

    G_output_path = os.path.join(output_dir, 'G.tif')

    G_meta = out_meta.copy()
    G_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': 'float32',
        'width': G.shape[1],
        'height': G.shape[0]
    })

    try:
        with rasterio.open(G_output_path, 'w', **G_meta) as dst:
            dst.write(G.astype('float32'), 1)
        print("G salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    print("Calculating soil heat flux (G) - W/m2... Done!")

    # Criação da Máscara do Pixel Quente (Phot)
    Phot = np.where((SAVI > 0.18) & (SAVI < 0.3), Ts, np.nan)

    Phot_output_path = os.path.join(output_dir, 'Phot.tif')

    Phot_meta = out_meta.copy()
    Phot_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': 'float32',
        'width': Phot.shape[1],
        'height': Phot.shape[0]
    })

    try:
        with rasterio.open(Phot_output_path, 'w', **Phot_meta) as dst:
            dst.write(Phot.astype('float32'), 1)
        print("Phot salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    # Solicitar as coordenadas de PHot
    try:
        ts_file_path = os.path.join(output_dir, 'Ts.tif')

        with rasterio.open(ts_file_path) as ts_src:
            # Solicitar as coordenadas de PHot
            phot_coords_str, ok = QInputDialog.getText(gui_dialog, 'Coordenadas PHot', 'Insira as coordenadas do PHot (easting, northing):')
            if not ok:
                QMessageBox.warning(gui_dialog, "Processamento Cancelado", "Processamento cancelado pelo usuário.")
                return
            row_phot, col_phot = ts_src.index(*map(float, phot_coords_str.strip().split(',')))
            z_TsPhot = ts_src.read(1)[row_phot, col_phot]
            print(f"Hot pixel temperature: {z_TsPhot} K")

            h = 0.15  # Altura do dossel
            Zom = 0.123 * h
            u_ast = 0.41 * u_2m / (math.log(2 / Zom))
            u_200m = u_ast * (math.log(200 / Zom)) / 0.41
            print("Calculating friction velocity (u*) for weather station - m/s... Done!")

    except Exception as e:
        print(f"Erro ao processar PHot: {e}")
        return

    # Cálculo de Z0map
    savi_file_path = os.path.join(output_dir, 'SAVI.tif')

    try:
        with rasterio.open(savi_file_path) as src_savi:
            SAVI = src_savi.read(1)

        Z0map = np.exp(-5.809 + 5.62 * SAVI)

        Z0map_output_path = os.path.join(output_dir, 'Z0map.tif')

        Z0map_meta = src_savi.meta.copy()
        Z0map_meta.update({
            'driver': 'GTiff',
            'count': 1,
            'dtype': 'float32',
            'width': Z0map.shape[1],
            'height': Z0map.shape[0]
        })

        with rasterio.open(Z0map_output_path, 'w', **Z0map_meta) as dst:
            dst.write(Z0map.astype('float32'), 1)
        print("Z0map salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao processar ou salvar os rasters: {e}")

    # Cálculo de u_astmap
    u_astmap = 0.41 * u_200m / np.log(200 / Z0map)

    u_astmap_output_path = os.path.join(output_dir, 'u_astmap.tif')

    u_astmap_meta = out_meta.copy()
    u_astmap_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': 'float32',
        'width': u_astmap.shape[1],
        'height': u_astmap.shape[0]
    })

    try:
        with rasterio.open(u_astmap_output_path, 'w', **u_astmap_meta) as dst:
            dst.write(u_astmap.astype('float32'), 1)
        print("u_astmap salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    print("Calculating the friction velocity map (u*map) - m/s... Done!")

    # Cálculo de rah
    rah = np.log(2 / 0.1) / (u_astmap * 0.41)
    print("Calculating aerodynamic resistance to heat transport map in terms of neutral stability (rah) - s/m... Done!")

    rah_output_path = os.path.join(output_dir, 'rah.tif')

    rah_meta = out_meta.copy()
    rah_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': 'float32',
        'width': rah.shape[1],
        'height': rah.shape[0]
    })

    try:
        with rasterio.open(rah_output_path, 'w', **rah_meta) as dst:
            dst.write(rah.astype('float32'), 1)
        print("rah salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    # Cálculo de dT
    # Estimativa inicial de dT usando uma relação linear entre Ts e dT
    # Inicialização dos valores
    z_rahPhot = rah[row_phot, col_phot]
    z_GPhot = G[row_phot, col_phot]
    z_RnPhot = Rn[row_phot, col_phot]

    z_rahPhot_i = 0
    i = 0
    while abs(z_rahPhot_i - z_rahPhot) > 0.00001 and i < 10:
        print("Iteration number:", i)
        i += 1
        z_rahPhot_i = z_rahPhot
        a = ((z_RnPhot - z_GPhot) * z_rahPhot_i) / ((z_TsPhot - z_TsPcold) * 1.25 * 1004)
        b = -a * z_TsPcold
        dT = a * Ts + b

        H = (1.25 * 1004 * dT) / rah

        # Recalcular z_rahPhot com os novos valores
        z_rahPhot = rah[row_phot, col_phot]
        print('a:', a, 'b:', b)

    dT_output_path = os.path.join(output_dir, 'dT.tif')

    dT_meta = out_meta.copy()
    dT_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': 'float32',
        'width': dT.shape[1],
        'height': dT.shape[0]
    })

    try:
        with rasterio.open(dT_output_path, 'w', **dT_meta) as dst:
            dst.write(dT.astype('float32'), 1)
        print("dT salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    # Cálculo de H
    H = (1.25 * 1004 * dT) / rah

    H_output_path = os.path.join(output_dir, 'H.tif')

    H_meta = out_meta.copy()
    H_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': 'float32',
        'width': H.shape[1],
        'height': H.shape[0]
    })

    try:
        with rasterio.open(H_output_path, 'w', **H_meta) as dst:
            dst.write(H.astype('float32'), 1)
        print("H salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    print("Calculating sensible heat flux (H) - W/m2... Done!")

    # Cálculo do Comprimento de Monin-Obukhov (L)
    g = 9.81  # Aceleração devido à gravidade
    L = -(1.25 * 1004 * Ts * u_astmap ** 3) / (0.41 * g * H)

    # Definir o caminho de saída para L
    L_output_path = os.path.join(output_dir, 'L.tif')

    # Preparar os metadados para salvar L
    L_meta = out_meta.copy()
    L_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': 'float32',
        'width': L.shape[1],
        'height': L.shape[0]
    })

    # Salvar L usando rasterio
    try:
        with rasterio.open(L_output_path, 'w', **L_meta) as dst:
            dst.write(L.astype('float32'), 1)
        print("L salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    print("Calculating the Monin-Obukhov length map (L) - m... Done!")

    # Cálculo das correções de estabilidade atmosférica (L200m, L2m, L01m)
    L200m = np.where(L < 0, 2 * np.log((1 + np.sqrt(1 - 16 * (200 / L))) / 2),
                     np.where(L > 0, -5 * (200 / L), 0))
    L2m = np.where(L < 0, 2 * np.log((1 + np.sqrt(1 - 16 * (2 / L))) / 2),
                   np.where(L > 0, -5 * (2 / L), 0))
    L01m = np.where(L < 0, 2 * np.log((1 + np.sqrt(1 - 16 * (0.1 / L))) / 2),
                    np.where(L > 0, -5 * (0.1 / L), 0))

    # Salvar L200m
    L200m_output_path = os.path.join(output_dir, 'L200m.tif')
    L200m_meta = out_meta.copy()
    L200m_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': 'float32',
        'width': L200m.shape[1],
        'height': L200m.shape[0]
    })

    try:
        with rasterio.open(L200m_output_path, 'w', **L200m_meta) as dst:
            dst.write(L200m.astype('float32'), 1)
        print("L200m salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    # Salvar L2m
    L2m_output_path = os.path.join(output_dir, 'L2m.tif')
    L2m_meta = out_meta.copy()
    L2m_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': 'float32',
        'width': L2m.shape[1],
        'height': L2m.shape[0]
    })

    try:
        with rasterio.open(L2m_output_path, 'w', **L2m_meta) as dst:
            dst.write(L2m.astype('float32'), 1)
        print("L2m salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    # Salvar L01m
    L01m_output_path = os.path.join(output_dir, 'L01m.tif')
    L01m_meta = out_meta.copy()
    L01m_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': 'float32',
        'width': L01m.shape[1],
        'height': L01m.shape[0]
    })

    try:
        with rasterio.open(L01m_output_path, 'w', **L01m_meta) as dst:
            dst.write(L01m.astype('float32'), 1)
        print("L01m salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    print("Calculating atmospheric stability correction (L200m, L2m, L01m)... Done!")

    # Cálculo de LET
    LET = Rn - G - H

    LET_output_path = os.path.join(output_dir, 'LET.tif')

    LET_meta = out_meta.copy()
    LET_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': 'float32',
        'width': LET.shape[1],
        'height': LET.shape[0]
    })

    try:
        with rasterio.open(LET_output_path, 'w', **LET_meta) as dst:
            dst.write(LET.astype('float32'), 1)
        print("LET salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    print("Calculating latent heat flux (LET) - W/m2... Done!")

    # Cálculo de ETi
    ETi = np.where(3600 * (LET / (2.45 * 1e6)) < 0, 0, 3600 * (LET / (2.45 * 1e6)))

    ETi_output_path = os.path.join(output_dir, 'ETi.tif')

    ETi_meta = out_meta.copy()
    ETi_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': 'float32',
        'width': ETi.shape[1],
        'height': ETi.shape[0]
    })

    try:
        with rasterio.open(ETi_output_path, 'w', **ETi_meta) as dst:
            dst.write(ETi.astype('float32'), 1)
        print("ETi salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    print("Calculating instantaneous evapotranspiration (ETi) - mm/h... Done!")

    # Cálculo de ETof
    ETof = ETi / EToi

    ETof_output_path = os.path.join(output_dir, 'ETof.tif')

    ETof_meta = out_meta.copy()
    ETof_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': 'float32',
        'width': ETof.shape[1],
        'height': ETof.shape[0]
    })

    try:
        with rasterio.open(ETof_output_path, 'w', **ETof_meta) as dst:
            dst.write(ETof.astype('float32'), 1)
        print("ETof salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    print("Calculating reference evapotranspiration fraction (ETof)... Done!")

    # Cálculo de ETday
    ETday = ETof * ETo

    ETday_output_path = os.path.join(output_dir, 'ETday.tif')

    ETday_meta = out_meta.copy()
    ETday_meta.update({
        'driver': 'GTiff',
        'count': 1,
        'dtype': 'float32',
        'width': ETday.shape[1],
        'height': ETday.shape[0]
    })

    try:
        with rasterio.open(ETday_output_path, 'w', **ETday_meta) as dst:
            dst.write(ETday.astype('float32'), 1)
        print("ETday salvo com sucesso.")
    except Exception as e:
        print(f"Erro ao escrever o arquivo TIFF: {e}")

    print("Calculating daily evapotranspiration (ETday) - mm/day... Done!")

    print("Processamento concluído com sucesso. Todos os produtos foram gerados.")
from time import perf_counter

import geopandas as gpd
import pandas as pd
import pyproj
from bloom.config import settings
from bloom.container import UseCases
from bloom.domain.port import Port
from bloom.infra.database.errors import DBException
from bloom.logger import logger
from shapely.geometry import Polygon

radius_m = 3000  # Radius in meters
resolution = 10  # Number of points in the resulting polygon


# Function to create geodesic buffer around a point
def geodesic_point_buffer(lat: float, lon: float, radius_m: int, resolution: int) -> Polygon:
    """
    Input
    lat: latitude of the center point
    lon: longitude of the center point
    radius_m: radius of the buffer in meters
    resolution: number of points in the resulting polygon
    """
    geod = pyproj.Geod(ellps="WGS84")  # Define the ellipsoid
    # Create a circle in geodesic coordinates
    angles = range(0, 360, 360 // resolution)
    circle_points = []
    for angle in angles:
        # Calculate the point on the circle for this angle
        lon2, lat2, _ = geod.fwd(lon, lat, angle, radius_m)
        circle_points.append((lon2, lat2))
    # Create a polygon from these points
    return Polygon(circle_points)


def run() -> None:
    use_cases = UseCases()
    port_repository = use_cases.port_repository()
    db = use_cases.db()
    total = 0
    ports = port_repository.get_empty_geometry_buffer_ports()
    if ports != []:
        try:
            df = pd.DataFrame(
                [[p.id, p.geometry_point, p.latitude, p.longitude] for p in ports],
                columns=["id", "geometry_point", "latitude", "longitude"],
            )
            gdf = gpd.GeoDataFrame(df, geometry="geometry_point", crs=settings.srid)

            # Apply the buffer function to create geodesic buffers
            gdf["geometry_buffer"] = gdf.apply(
                lambda row: geodesic_point_buffer(
                    float(row["latitude"]),
                    float(row["longitude"]),
                    radius_m,
                    resolution,
                ),
                axis=1,
            )
            with db.session() as session:
                for row in gdf.itertuples():
                    port_repository.update_geometry_buffer(row.id, row.geometry_buffer, session)
                    total += 1
                session.commit()
        except DBException as e:
            logger.error("Erreur de mise à jour en base")
    logger.info(f"{total} buffer de ports mis à jour")


if __name__ == "__main__":
    time_start = perf_counter()
    logger.info("DEBUT - Calcul des buffer de ports")
    run()
    time_end = perf_counter()
    duration = time_end - time_start
    logger.info(f"FIN - Calcul des buffer de ports en {duration:.2f}s")

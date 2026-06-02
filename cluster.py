import numpy as np
import geopandas as gpd
from shapely.geometry import Point, MultiPoint

def get_centroid(buses):
    return MultiPoint(list(buses['pos'])).centroid

def cluster(points, r):

    def distance(p, points):
        return np.linalg.norm(points - p, axis=1)

    def within_range(p, points, r):
        return distance(p, points) <= r

    def get_cluster(points, r, local_idxs, current_cluster=None, depth=0):

        if current_cluster is None:
            current_cluster = []

        for idx in local_idxs:
            if idx not in remaining_idxs:
                continue

            current_cluster.append(idx)
            remaining_idxs.remove(idx)  # do not take this point into account

            # find remaining points within range
            nearby_mask = within_range(points[idx, 1:], points[np.array(remaining_idxs, dtype=int), 1:], r=r)

            if nearby_mask.any():  # found some points nearby, expand search
                nearby_idxs = np.array(remaining_idxs, int)[nearby_mask].tolist()
                get_cluster(points, r=r, local_idxs=nearby_idxs, current_cluster=current_cluster, depth=depth+1)
            
            if depth == 0:  # nothing to add to this cluster anymore, closing cluster
                clusters.append(current_cluster)
                current_cluster = []
        
        # finished search
        return


    remaining_idxs = np.array(points[:, 0], int).tolist()
    clusters = []
    get_cluster(points, r=r, local_idxs=remaining_idxs.copy())
    
    return clusters


def numpy_test():

    num_points = 20
    r = 0.2
    points = np.empty(shape=[num_points, 3])
    points[:, 0] = np.arange(points.shape[0])
    points[:, 1:] = np.random.rand(num_points, 2)

    clusters = cluster(points, r=r)

    return points, clusters, r


def cluster_buses(buses, r):
    idxs_old = buses.index

    xs = buses['pos'].apply(lambda pt: pt.x)
    ys = buses['pos'].apply(lambda pt: pt.y)

    idx_new = list(range(len(xs)))
    points = np.column_stack((idx_new, xs, ys))

    clusters = cluster(points, r=r)

    clusters_mapped = [idxs_old[np.array(c, int)] for c in clusters]

    return clusters_mapped


def bus_test():
    import geopandas as gpd
    from shapely.geometry import Point

    buses = gpd.GeoDataFrame({
        'pos': [Point(0, 0), Point(10, 10), Point(5, 5), Point(50, 50), Point(55, 55)],
        }, index = [2, 1, 4, 7, 9], geometry='pos')
    
    idxs = buses.index
    xs = buses['pos'].x
    ys = buses['pos'].y
    points = np.column_stack((idxs, xs, ys))
    
    r = 40
    clusters = cluster_buses(buses, r)
    
    return points, clusters, r


def __main__():
    import matplotlib.pyplot as plt

    # numpy_test()
    points, clusters, r = bus_test()

    print(f"number of clusters: {len(clusters)}")
    print(clusters)

    plt.figure()
    for i, c in enumerate(clusters):
        idxs = np.array([np.where(points[:,0] == j)[0][0] for j in c])
        x = points[idxs, 1]
        y = points[idxs, 2]
        plt.scatter(x, y, label=f"Cluster {i}")

    plt.title(f"range: {r}")

    plt.show()


if __name__ == "__main__":
    __main__()
import random
from collections import defaultdict
from math import sqrt

import requests

from database import getclusterLevelResultCollection, getClusterCollection, getPageDataCollection
from utilities import access_token, getAppendString, KVAL, PID


def densify(x, n):
    d = [0] * n
    for i, v in x:
        d[i] = v
    return d


def dist(x, c):
    sqdist = 0.
    for i, v in x:
        sqdist += (v - c[i]) ** 2
    return sqrt(sqdist)


def mean(xs, l):
    c = [0.] * l
    n = 0
    for x in xs:
        for i, v in x:
            c[i] += v
        n += 1
    for i in xrange(l):
        c[i] /= n
    return c


def kmeans(k, xs, l, n_iter=10):
    # Initialize from random points.
    centers = [densify(xs[i], l) for i in random.sample(xrange(len(xs)), k)]
    cluster = [None] * len(xs)

    for _ in xrange(n_iter):
        for i, x in enumerate(xs):
            cluster[i] = min(xrange(k), key=lambda j: dist(xs[i], centers[j]))
        for j, c in enumerate(centers):
            members = (x for i, x in enumerate(xs) if cluster[i] == j)
            centers[j] = mean(members, l)

    return cluster


def getdata(data, string):
    if string in data:
        return data[string]
    return None


def fetchTestpage(fbid):
    global url
    trurl = url + '/v2.3/'
    rurl = str(trurl) + str(fbid)
    response = requests.get(rurl, params={'access_token': access_token,
                                          'fields': 'about,category,bio,name,posts.limit(10){message}'})
    data = response.json()
    if 'posts' not in data:
        data['posts'] = {}
        data['posts']['data'] = []
    document = {
        '_id': fbid,
        'name': getdata(data, 'name'),
        'about': getdata(data, 'about'),
        'category': getdata(data, 'category'),
        'bio': getdata(data, 'bio'),
        'posts': [getdata(msg, 'message') for msg in data['posts']['data']]
    }
    string = getAppendString(document)
    f = open('temp/' + str(string['_id']) + '.txt', 'w')
    f.write(string['data'])
    f.close()


if __name__ == '__main__':
    # Cluster a bunch of text documents.
    import re
    import sys
    import glob


    def usage():
        print("usage: %s k docs..." % sys.argv[0])
        print("    The number of documents must be >= k.")
        sys.exit(1)


    try:
        k = KVAL
    except ValueError():
        usage()

    vocab = {}
    xs = []
    args = []
    fid = ''
    fetchTestpage(PID)

    clusterCollection = getClusterCollection()

    clusters = clusterCollection.distinct("cluster")

    fbdataCollection = getPageDataCollection()
    for cluster in clusterCollection.find():
        pageIds = cluster['pages'][:len(cluster['pages']) / 10]
        for p in pageIds:
            data = fbdataCollection.find_one({'_id': p})
            _id = data['_id']
            string = data['data']
            f = open('temp/' + _id + '.txt', 'w')
            f.write(string)
            f.close()

    for name in glob.glob('./temp/*.txt'):
        args.append(name)

    for a in args:
        x = defaultdict(float)
        with open(a) as f:
            for w in re.findall(r"\w+", f.read()):
                vocab.setdefault(w, len(vocab))
                x[vocab[w]] += 1
        xs.append(x.items())

    cluster_ind = kmeans(k, xs, len(vocab))
    clusters = [set() for _ in xrange(k)]
    for i, j in enumerate(cluster_ind):
        clusters[j].add(i)


    def cleanName(string):
        return string[7:-4]


    # collection.drop()
    for j, c in enumerate(clusters):
        # print("cluster %d:" % j)
        array = []
        for i in c:
            # print("\t%s" % args[i])
            array.append(args[i])
            if cleanName(args[i]) == PID:
                cluster = j
                break
        array = map(cleanName, array)
        doc = {'cluster': j, 'pages': array}
    # print "Cluster", cluster

    clusterCollection = getclusterLevelResultCollection()
    count = 0

    f = open('tempfile.txt', 'w')
    f.write("Influencers for this cluster are\n")

    ct = 0
    for influ in clusterCollection.find({'_id': str(cluster)}):
        for each in influ['users']:
            ct += 1
            if ct <= 5:
                f.write(each['name'], each['id'], '\n')
            else:
                break
    print 'done'

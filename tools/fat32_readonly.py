"""Bounded FAT32 8.3 file reader for existing boot evidence. No write interface.

Independent implementation from on-disk format definitions in Microsoft's EFI
FAT32 specification v1.03 and Mu FatFileSystem.h. No third-party code copied.
"""
import struct


class Fat32Reader:
    def __init__(self, stream, size, block_size=512):
        self.stream, self.size, self.block = stream, size, block_size
        if block_size not in (512, 1024, 2048, 4096, 8192, 16384, 32768, 65536):
            raise ValueError('Unsupported device block size')
        b = self.read_at(0, 512)
        u16 = lambda offset: struct.unpack_from('<H', b, offset)[0]
        u32 = lambda offset: struct.unpack_from('<I', b, offset)[0]
        self.sector, spc, reserved, self.fats = u16(11), b[13], u16(14), b[16]
        self.fat_sectors, self.root, self.total = u32(36), u32(44), u32(32)
        flags = u16(40)
        if (b[510:512] != b'\x55\xaa' or self.sector not in (512,1024,2048,4096) or
                spc == 0 or spc & (spc-1) or spc > 128 or reserved == 0 or
                self.fats not in (1,2) or not self.fat_sectors or
                u16(17) != 0 or u16(19) != 0 or u16(22) != 0 or u16(42) != 0):
            raise ValueError('Not a supported FAT32 BPB')
        self.cluster_size = self.sector*spc
        self.data_sector = reserved+self.fats*self.fat_sectors
        self.clusters = (self.total-self.data_sector)//spc
        if (self.cluster_size > 65536 or self.total*self.sector > size or
                not 65525 <= self.clusters < 0x0ffffff5 or
                self.fat_sectors*self.sector//4 < self.clusters+2):
            raise ValueError('FAT32 geometry exceeds the partition or FAT capacity')
        self.mirrored = not bool(flags & 0x80)
        self.active = 0 if self.mirrored else flags & 15
        if self.active >= self.fats:
            raise ValueError('Invalid active FAT index')
        self.fat_start = reserved*self.sector
        self.fat_bytes = self.fat_sectors*self.sector
        self._cache = {}
        self.check_cluster(self.root)

    def read_at(self, offset, count):
        if count < 0 or offset < 0 or offset+count > self.size:
            raise ValueError('Read outside the measured partition')
        first = offset//self.block*self.block
        last = (offset+count+self.block-1)//self.block*self.block
        if last > self.size:
            raise ValueError('Aligned read exceeds measured partition')
        self.stream.seek(first)
        data = self.stream.read(last-first)
        if len(data) != last-first:
            raise ValueError('Short partition read')
        return data[offset-first:offset-first+count]

    def check_cluster(self, cluster):
        if not 2 <= cluster < self.clusters+2:
            raise ValueError('Invalid FAT32 cluster')

    def fat_entry(self, cluster, copy):
        position = cluster*4
        sector = position//self.sector
        key = (copy, sector)
        if key not in self._cache:
            if len(self._cache) >= 4096:
                raise ValueError('FAT read budget exceeded')
            self._cache[key] = self.read_at(self.fat_start+copy*self.fat_bytes+sector*self.sector,self.sector)
        return struct.unpack_from('<I',self._cache[key],position % self.sector)[0] & 0x0fffffff

    def next_cluster(self, cluster):
        value = self.fat_entry(cluster,self.active)
        if self.mirrored and any(self.fat_entry(cluster,i) != value for i in range(self.fats)):
            raise ValueError('Mirrored FAT chain disagrees; refusing to choose a copy')
        if value >= 0x0ffffff8:
            return None
        self.check_cluster(value)
        return value

    def chain(self, cluster, budget):
        seen = set()
        while cluster is not None:
            self.check_cluster(cluster)
            if cluster in seen or len(seen) >= budget:
                raise ValueError('Cyclic or over-budget FAT chain')
            seen.add(cluster)
            offset = (self.data_sector+(cluster-2)*(self.cluster_size//self.sector))*self.sector
            yield self.read_at(offset,self.cluster_size)
            cluster = self.next_cluster(cluster)

    @staticmethod
    def short_name(component):
        pieces = component.upper().split('.')
        if (not 1 <= len(pieces) <= 2 or not 1 <= len(pieces[0]) <= 8 or
                (len(pieces)==2 and not 1 <= len(pieces[1]) <= 3) or
                any(not (c.isascii() and (c.isalnum() or c=='_')) for p in pieces for c in p)):
            raise ValueError('Only fixed ASCII 8.3 evidence paths are supported')
        return (pieces[0].ljust(8)+(pieces[1] if len(pieces)==2 else '').ljust(3)).encode('ascii')

    def find(self, directory, component):
        wanted = self.short_name(component)
        matches = []
        ended = False
        for data in self.chain(directory, max(1,262144//self.cluster_size)):
            for offset in range(0,len(data),32):
                entry = data[offset:offset+32]
                if entry[0] == 0:
                    ended = True
                    break
                if entry[0] == 0xe5 or entry[11] == 0x0f or entry[11] & 8:
                    continue
                if entry[:11] == wanted:
                    cluster = struct.unpack_from('<H',entry,20)[0]<<16 | struct.unpack_from('<H',entry,26)[0]
                    matches.append((entry[11],cluster,struct.unpack_from('<I',entry,28)[0]))
            if ended:
                break
        if not matches:
            raise FileNotFoundError(component)
        if len(matches) != 1:
            raise ValueError('Duplicate short evidence path')
        return matches[0]

    def read_file(self, path, max_size):
        parts = path.split('/')
        if len(parts) != 2 or any(p in ('','.', '..') for p in parts):
            raise ValueError('Expected one fixed directory and file')
        attr,directory,_ = self.find(self.root,parts[0])
        if not attr & 0x10:
            raise ValueError('Evidence parent is not a directory')
        attr,cluster,size = self.find(directory,parts[1])
        if attr & 0x10 or size > max_size:
            raise ValueError('Evidence file type or size is invalid')
        if not size:
            return b''
        chunks = []
        remaining = size
        for data in self.chain(cluster,(size+self.cluster_size-1)//self.cluster_size):
            chunks.append(data[:remaining])
            remaining -= min(remaining,len(data))
            if not remaining:
                return b''.join(chunks)
        raise ValueError('Evidence file chain is truncated')

    def geometry(self):
        state = [self.fat_entry(1,i) for i in range(self.fats)]
        return {'sector_size':self.sector,'cluster_size':self.cluster_size,
                'cluster_count':self.clusters,'active_fat':self.active,'mirrored':self.mirrored,
                'fat_state_entries':state,'clean_shutdown_flags':[bool(v & 0x08000000) for v in state]}

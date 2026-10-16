// EvtWin7: 宽读邻接检查 + 控制台注册表搜寻（字符串全景）
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class EvtWin7 extends GhidraScript {

    List<Long> findPattern(byte[] pat) throws Exception {
        List<Long> hits = new ArrayList<>();
        int keep = pat.length - 1;
        for (MemoryBlock blk : currentProgram.getMemory().getBlocks()) {
            if (!blk.isInitialized()) {
                continue;
            }
            long start = blk.getStart().getOffset();
            long end = blk.getEnd().getOffset();
            int chunk = 1 << 22;
            byte[] buf = new byte[chunk];
            byte[] carry = new byte[0];
            long pos = start;
            outer:
            while (pos <= end) {
                int want = (int) Math.min(chunk, end - pos + 1);
                int got;
                try {
                    got = blk.getBytes(toAddr(pos), buf, 0, want);
                } catch (Exception e) {
                    break;
                }
                if (got <= 0) {
                    break;
                }
                byte[] data = new byte[carry.length + got];
                System.arraycopy(carry, 0, data, 0, carry.length);
                System.arraycopy(buf, 0, data, carry.length, got);
                long baseVa = pos - carry.length;
                for (int i = 0; i + pat.length <= data.length; i++) {
                    boolean ok = true;
                    for (int j = 0; j < pat.length; j++) {
                        if (data[i + j] != pat[j]) {
                            ok = false;
                            break;
                        }
                    }
                    if (ok) {
                        hits.add(baseVa + i);
                        if (hits.size() > 120) {
                            break outer;
                        }
                    }
                }
                if (got < want) {
                    break;
                }
                pos += got;
                int k = Math.min(keep, data.length);
                carry = Arrays.copyOfRange(data, data.length - k, data.length);
            }
        }
        return hits;
    }

    void refsOf(long va) {
        int n = 0;
        for (Reference r : getReferencesTo(toAddr(va))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("      " + r.getReferenceType() + " from " + r.getFromAddress()
                    + " in " + (f != null ? f.getName() + "@0x" + Long.toHexString(f.getEntryPoint().getOffset()) : "?"));
            if (++n >= 14) {
                println("      ...");
                break;
            }
        }
        if (n == 0) {
            println("      (no refs)");
        }
    }

    void decompileFn(long va, int cap) {
        Function f = getFunctionContaining(toAddr(va));
        if (f == null) {
            println("  (no function @0x" + Long.toHexString(va) + ")");
            return;
        }
        println("==== decompile " + f.getName() + " @0x" + Long.toHexString(f.getEntryPoint().getOffset()) + " (cap " + cap + ") ====");
        try {
            DecompInterface dec = new DecompInterface();
            dec.openProgram(currentProgram);
            DecompileResults res = dec.decompileFunction(f, 90, monitor);
            if (res != null && res.decompileCompleted()) {
                String[] lines = res.getDecompiledFunction().getC().split("\n");
                for (int i = 0; i < Math.min(lines.length, cap); i++) {
                    println("  " + lines[i]);
                }
                if (lines.length > cap) {
                    println("  ... (" + (lines.length - cap) + " more lines)");
                }
            } else {
                println("  (decompile failed)");
            }
            dec.dispose();
        } catch (Exception e) {
            println("  (decompile error " + e + ")");
        }
    }

    @Override
    public void run() throws Exception {
        // 1) 宽读邻接检查
        long[] neigh = { 0x142814838L, 0x142814837L, 0x142814835L };
        for (long va : neigh) {
            println("==== refs to 0x" + Long.toHexString(va) + " ====");
            refsOf(va);
        }

        // 2) 字符串全景
        String[] needles = {
            "human_ai", "humanai", "instant_build", "finish_research",
            "research_technology", "Unknown command", "unknown command",
            "debugtooltip", "berserk", "fullgalaxyspawn"
        };
        Map<String, List<Long>> found = new LinkedHashMap<>();
        for (String s : needles) {
            List<Long> hits = findPattern(s.getBytes("US-ASCII"));
            found.put(s, hits);
            println("==== string '" + s + "' hits=" + hits.size() + " ====");
            for (long h : hits) {
                println("  @0x" + Long.toHexString(h));
                refsOf(h);
            }
        }

        // 3) 若找到 research_technology，反编译其引用者
        List<Long> rt = found.get("research_technology");
        if (rt != null) {
            for (long h : rt) {
                for (Reference r : getReferencesTo(toAddr(h))) {
                    Function f = getFunctionContaining(r.getFromAddress());
                    if (f != null) {
                        decompileFn(f.getEntryPoint().getOffset(), 90);
                    }
                }
            }
        }
        println("==== done ====");
    }
}
